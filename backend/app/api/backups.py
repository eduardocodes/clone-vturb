import os
import tempfile
import logging
from typing import List
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.backup import BackupRecord, BackupSchedule
from app.schemas.backup import (
    BackupRecordResponse,
    BackupScheduleResponse,
    UpdateScheduleRequest,
    BackupMetricsResponse,
    BulkDeleteBackupsRequest,
    BulkDeleteBackupsResponse,
)
from app.services.backup_manager import BackupManager
from app.services.backblaze import backblaze_backup_service
from app.api.users import require_super_admin, require_super_admin_allow_query_token

logger = logging.getLogger("projetovturb")

router = APIRouter()

def calculate_next_backup_time(schedule: BackupSchedule, now: datetime = None) -> datetime:
    """Calcula o próximo horário de backup com base na frequência e intervalo configurados."""
    if not now:
        now = datetime.now(timezone.utc)
    base_time = schedule.last_backup_at or now

    if schedule.frequency == "hours":
        delta = timedelta(hours=schedule.interval_value)
    elif schedule.frequency == "days":
        delta = timedelta(days=schedule.interval_value)
    elif schedule.frequency == "weekly":
        delta = timedelta(weeks=schedule.interval_value)
    else:
        delta = timedelta(hours=6)

    next_time = base_time + delta
    # Se o horário calculado já passou em relação ao momento atual, agenda a partir de agora
    if next_time <= now:
        next_time = now + delta
    return next_time

@router.get("/", response_model=List[BackupRecordResponse])
def list_backups(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Lista todos os backups registrados no sistema, ordenados pelo mais recente."""
    return db.query(BackupRecord).order_by(BackupRecord.created_at.desc()).all()

@router.get("/metrics", response_model=BackupMetricsResponse)
def get_backup_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Retorna dados consolidados para os cards de métricas do topo do painel."""
    last_backup = db.query(BackupRecord).order_by(BackupRecord.created_at.desc()).first()
    total_count = db.query(BackupRecord).count()

    now = datetime.now(timezone.utc)
    schedule = db.query(BackupSchedule).first()
    retention = schedule.retention_limit if schedule else 30
    next_at = None

    if schedule and schedule.is_active:
        if not schedule.next_backup_at or schedule.next_backup_at <= now:
            schedule.next_backup_at = calculate_next_backup_time(schedule, now)
            db.commit()
            db.refresh(schedule)
        next_at = schedule.next_backup_at

    freq_text = "A cada 6 hora(s)"
    if schedule:
        unit = "hora(s)" if schedule.frequency == "hours" else "dia(s)" if schedule.frequency == "days" else "semana(s)"
        freq_text = f"A cada {schedule.interval_value} {unit}"

    storage_ok = backblaze_backup_service.is_configured()
    storage_msg = (
        "Backblaze B2 conectado com sucesso."
        if storage_ok
        else "Backblaze B2 não configurado ou credenciais pendentes no .env."
    )

    return BackupMetricsResponse(
        last_backup_filename=last_backup.filename if last_backup else None,
        last_backup_at=last_backup.created_at if last_backup else None,
        next_backup_at=next_at,
        frequency_text=freq_text,
        retention_limit=retention,
        total_backups=total_count,
        storage_configured=storage_ok,
        storage_message=storage_msg,
    )

@router.post("/create", response_model=BackupRecordResponse)
def create_manual_backup(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Gera um snapshot manual imediato do banco PostgreSQL e envia para o Backblaze B2."""
    try:
        record = BackupManager.create_database_dump(db, is_manual=True)
        logger.info(f"Backup manual criado com sucesso: {record.filename}")
        return record
    except Exception as e:
        logger.error(f"Falha ao criar backup manual: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao gerar backup. Consulte os logs do servidor."
        )

@router.get("/schedule", response_model=BackupScheduleResponse)
def get_backup_schedule(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Retorna as configurações atuais da rotina de agendamento automático."""
    schedule = db.query(BackupSchedule).first()
    if not schedule:
        schedule = BackupSchedule(
            id=1,
            is_active=True,
            frequency="hours",
            interval_value=6,
            s3_folder="vturb/backups/",
            retention_limit=30,
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
    return schedule

@router.put("/schedule", response_model=BackupScheduleResponse)
def update_backup_schedule(
    payload: UpdateScheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Atualiza as configurações da rotina de agendamento automático."""
    schedule = db.query(BackupSchedule).first()
    if not schedule:
        schedule = BackupSchedule(id=1)
        db.add(schedule)

    now = datetime.now(timezone.utc)
    schedule.is_active = payload.is_active
    schedule.frequency = payload.frequency
    schedule.interval_value = payload.interval_value
    schedule.s3_folder = payload.s3_folder.strip()
    schedule.retention_limit = payload.retention_limit
    schedule.updated_at = now

    if schedule.is_active:
        schedule.next_backup_at = calculate_next_backup_time(schedule, now)
    else:
        schedule.next_backup_at = None

    db.commit()
    db.refresh(schedule)
    logger.info(f"Configuração de agendamento de backup atualizada com sucesso. Próximo backup: {schedule.next_backup_at}")
    return schedule

@router.get("/{backup_id}/download")
def download_backup(
    backup_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin_allow_query_token),
):
    """Baixa o arquivo compactado de dump (.dump.gz)."""
    record = db.query(BackupRecord).filter(BackupRecord.id == backup_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Backup não encontrado.")

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".dump.gz")
    temp_path = Path(temp_file.name)
    temp_file.close()

    try:
        backblaze_backup_service.download_backup_file(record.storage_path, temp_path)
        return FileResponse(
            path=str(temp_path),
            filename=record.filename,
            media_type="application/gzip",
            background=BackgroundTask(temp_path.unlink, missing_ok=True),
        )
    except Exception as e:
        logger.error(f"Erro no download do backup {backup_id}: {e}")
        raise HTTPException(status_code=500, detail="Falha ao obter arquivo para download.")

@router.post("/{backup_id}/restore")
def restore_backup(
    backup_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Restaura o banco de dados a partir do dump selecionado."""
    record = db.query(BackupRecord).filter(BackupRecord.id == backup_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Backup não encontrado.")

    try:
        BackupManager.restore_database_dump(db, backup_id)
        return {"detail": f"Banco de dados restaurado com sucesso a partir de {record.filename}."}
    except Exception as e:
        logger.error(f"Falha na restauração do backup {backup_id}: {e}")
        raise HTTPException(status_code=500, detail="Erro na restauração. Consulte os logs do servidor.")

@router.delete("/{backup_id}")
def delete_backup(
    backup_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Exclui um backup do Backblaze S3 e remove o registro do banco."""
    if not backblaze_backup_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Backblaze B2 não está conectado. Configure as credenciais de armazenamento (BACKBLAZE_KEY_ID, BACKBLAZE_APPLICATION_KEY, BACKBLAZE_BUCKET_NAME, BACKBLAZE_ENDPOINT_URL) no servidor para poder gerenciar e excluir backups da nuvem com segurança."
        )

    record = db.query(BackupRecord).filter(BackupRecord.id == backup_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Backup não encontrado.")

    try:
        backblaze_backup_service.delete_backup_file(record.storage_path)
    except Exception as e:
        logger.warning(f"Erro ao remover arquivo físico do S3: {e}")

    db.delete(record)
    db.commit()
    return {"detail": "Backup excluído com sucesso."}

@router.post("/bulk-delete", response_model=BulkDeleteBackupsResponse)
def bulk_delete_backups(
    payload: BulkDeleteBackupsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Exclui múltiplos backups em lote do Backblaze S3 e do banco."""
    if not payload.ids:
        return BulkDeleteBackupsResponse(deleted_count=0, deleted_ids=[])

    if not backblaze_backup_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Backblaze B2 não está conectado. Configure as credenciais de armazenamento no servidor para poder excluir backups em lote com segurança."
        )

    records = db.query(BackupRecord).filter(BackupRecord.id.in_(payload.ids)).all()
    deleted_ids = []

    for r in records:
        try:
            backblaze_backup_service.delete_backup_file(r.storage_path)
        except Exception as e:
            logger.warning(f"Erro ao excluir arquivo físico de backup: {e}")
        deleted_ids.append(r.id)
        db.delete(r)

    db.commit()
    logger.info(f"{len(deleted_ids)} backups excluídos em lote.")
    return BulkDeleteBackupsResponse(deleted_count=len(deleted_ids), deleted_ids=deleted_ids)

@router.post("/upload", response_model=BackupRecordResponse)
async def upload_external_backup(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Recebe um arquivo de dump externo (.dump, .dump.gz, .sql) e envia para o Backblaze S3."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nome do arquivo inválido.")

    ext = Path(file.filename).suffix.lower()
    if ext not in [".gz", ".dump", ".sql"]:
        raise HTTPException(status_code=400, detail="Formato não suportado. Envie arquivos .dump, .dump.gz ou .sql.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    try:
        record = BackupManager.import_external_dump(db, file.filename, content)
        return record
    except Exception as e:
        logger.error(f"Erro ao processar upload externo de backup: {e}")
        raise HTTPException(status_code=500, detail="Erro ao importar backup. Consulte os logs do servidor.")
