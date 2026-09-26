import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.api.deps import get_current_user, get_current_user_allow_query_token
from app.core.security import hash_password
from app.models.user import User, UserInvite, PasswordResetToken
from app.schemas.auth import (
    UserResponse,
    CreateInviteRequest,
    InviteResponse,
    BulkDeleteRequest,
    BulkDeleteResponse,
    UpdateUserRequest,
    ResetPasswordTriggerResponse,
)
from app.services.brevo import send_password_reset_email

logger = logging.getLogger("projetovturb.users")
router = APIRouter(prefix="/users", tags=["Gestão de Usuários"])

def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    """Valida se o usuário autenticado é estritamente o Super Admin oficial ou possui privilégios de Super Admin."""
    return _ensure_super_admin(current_user)


def require_super_admin_allow_query_token(
    current_user: User = Depends(get_current_user_allow_query_token),
) -> User:
    """Super Admin autenticado por header ou ?token= (links de download abertos no navegador)."""
    return _ensure_super_admin(current_user)


def _ensure_super_admin(current_user: User) -> User:
    official_email = settings.SUPER_ADMIN_EMAIL.strip().lower()
    is_official = (
        bool(current_user.is_super_admin) or
        current_user.role == "super_admin" or
        current_user.email.strip().lower() == official_email
    )
    if not is_official:
        logger.warning(f"Acesso negado à Gestão de Usuários para {current_user.email} (não é Super Admin)")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito exclusivamente ao Super Admin."
        )
    return current_user


@router.get("/", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Lista todos os usuários cadastrados no sistema, garantindo um único SuperAdmin oficial sempre no topo."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    official_email = settings.SUPER_ADMIN_EMAIL.strip().lower()

    super_admin_user = None
    common_users = []

    for u in users:
        if u.email.strip().lower() == official_email:
            u.role = "super_admin"
            u.is_super_admin = True
            if not u.name:
                u.name = "Super Admin"
            super_admin_user = u
        else:
            common_users.append(u)

    if super_admin_user:
        return [super_admin_user] + common_users
    return common_users

@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: UpdateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Edita dados de um usuário (nome, e-mail, função ou senha). O SuperAdmin não pode ser editado."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado."
        )

    official_email = settings.SUPER_ADMIN_EMAIL.strip().lower()
    if user.is_super_admin or user.role == "super_admin" or user.email.strip().lower() == official_email:
        logger.warning(f"Tentativa de editar Super Admin ({user.email}) bloqueada.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O Super Admin oficial não pode ser editado."
        )

    if payload.role is not None:
        role_clean = payload.role.strip().lower()
        if role_clean == "super_admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não é permitido atribuir a função Super Admin."
            )
        if role_clean not in ["admin", "user"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Função inválida. Escolha entre 'admin' ou 'user'."
            )
        user.role = role_clean

    if payload.name is not None:
        user.name = payload.name.strip() or None

    if payload.email is not None:
        email_clean = payload.email.strip().lower()
        if email_clean != user.email.lower():
            existing = db.query(User).filter(User.email.ilike(email_clean), User.id != user.id).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Este endereço de e-mail já está sendo utilizado por outro usuário."
                )
            user.email = email_clean

    if payload.password is not None and payload.password.strip():
        if len(payload.password.strip()) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A nova senha deve ter no mínimo 8 caracteres."
            )
        user.password_hash = hash_password(payload.password.strip())

    db.commit()
    db.refresh(user)
    logger.info(f"Usuário {user.email} atualizado com sucesso pelo Super Admin {current_user.email}")
    return user

@router.post("/{user_id}/reset-password", response_model=ResetPasswordTriggerResponse)
def trigger_user_password_reset(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Inicia o processo de redefinição de senha para um usuário pelo Super Admin."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado."
        )

    official_email = settings.SUPER_ADMIN_EMAIL.strip().lower()
    if user.is_super_admin or user.role == "super_admin" or user.email.strip().lower() == official_email:
        logger.warning(f"Tentativa de redefinir senha do Super Admin ({user.email}) bloqueada.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é permitido redefinir a senha do Super Admin oficial por este método."
        )

    # Invalida tokens anteriores pendentes deste usuário
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.is_used.is_(False)
    ).update({"is_used": True})

    # Cria novo token seguro
    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    token_record = PasswordResetToken(
        user_id=user.id,
        token=reset_token,
        expires_at=expires_at,
        is_used=False
    )
    db.add(token_record)
    db.commit()

    reset_url = f"/reset-password?token={reset_token}"
    send_password_reset_email(to_email=user.email, reset_url=reset_url, to_name=user.name)

    logger.info(f"Redefinição de senha solicitada para {user.email} pelo Super Admin {current_user.email}")
    return ResetPasswordTriggerResponse(
        success=True,
        message=f"Instruções de redefinição de senha geradas e enviadas para {user.email}.",
        token=reset_token,
        reset_url=reset_url
    )

@router.delete("/{user_id}")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Exclui um usuário do sistema. O SuperAdmin NUNCA pode ser excluído."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado."
        )

    if user.is_super_admin or user.role == "super_admin":
        logger.warning(f"Tentativa bloqueada de excluir Super Admin ({user.email}) por {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O Super Admin não pode ser excluído."
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode excluir sua própria conta."
        )

    user_email = user.email
    db.delete(user)
    db.commit()
    logger.info(f"Usuário {user_email} excluído com sucesso por {current_user.email}")
    return {"detail": f"Usuário {user_email} excluído com sucesso."}

@router.post("/invites", response_model=InviteResponse)
def create_invite(
    payload: CreateInviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Gera um link de convite para um novo usuário (Admin ou Usuário) com tempo de expiração."""
    role_normalized = payload.role.strip().lower()
    if role_normalized not in ["admin", "user"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Perfil de convite inválido. Apenas 'admin' e 'user' são permitidos. SuperAdmin não pode ser criado via convite."
        )

    if payload.duration_hours <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O tempo de expiração do convite deve ser maior que zero."
        )

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=payload.duration_hours)

    invite = UserInvite(
        token=token,
        role=role_normalized,
        expires_at=expires_at,
        is_used=False,
        created_by_user_id=current_user.id,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    logger.info(f"Convite gerado para role '{role_normalized}' com expiração em {expires_at} por {current_user.email}")

    response = InviteResponse.model_validate(invite)
    response.invite_url = f"/invite/{token}"
    return response

@router.get("/invites", response_model=List[InviteResponse])
def list_invites(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Lista todos os convites gerados e seus status."""
    invites = db.query(UserInvite).order_by(UserInvite.created_at.desc()).all()
    results = []
    for inv in invites:
        item = InviteResponse.model_validate(inv)
        item.invite_url = f"/invite/{inv.token}"
        results.append(item)
    return results

@router.delete("/invites/{invite_id}")
def delete_invite(
    invite_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Exclui um link de convite."""
    invite = db.query(UserInvite).filter(UserInvite.id == invite_id).first()
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Convite não encontrado."
        )
    db.delete(invite)
    db.commit()
    logger.info(f"Convite {invite_id} excluído com sucesso por {current_user.email}")
    return {"detail": "Convite excluído com sucesso."}

@router.post("/bulk-delete", response_model=BulkDeleteResponse)
def bulk_delete_users(
    payload: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Exclui múltiplos usuários de uma só vez, protegendo o SuperAdmin e o usuário logado."""
    if not payload.ids:
        return BulkDeleteResponse(deleted_count=0, deleted_ids=[])

    official_email = settings.SUPER_ADMIN_EMAIL.strip().lower()
    users_to_delete = db.query(User).filter(User.id.in_(payload.ids)).all()
    deleted_ids = []

    for u in users_to_delete:
        if u.is_super_admin or u.role == "super_admin" or u.email.strip().lower() == official_email:
            continue
        if u.id == current_user.id:
            continue
        deleted_ids.append(u.id)
        db.delete(u)

    db.commit()
    logger.info(f"{len(deleted_ids)} usuários excluídos em massa por {current_user.email}")
    return BulkDeleteResponse(deleted_count=len(deleted_ids), deleted_ids=deleted_ids)

@router.post("/invites/bulk-delete", response_model=BulkDeleteResponse)
def bulk_delete_invites(
    payload: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Exclui múltiplos convites de uma só vez."""
    if not payload.ids:
        return BulkDeleteResponse(deleted_count=0, deleted_ids=[])

    invites_to_delete = db.query(UserInvite).filter(UserInvite.id.in_(payload.ids)).all()
    deleted_ids = [inv.id for inv in invites_to_delete]

    for inv in invites_to_delete:
        db.delete(inv)

    db.commit()
    logger.info(f"{len(deleted_ids)} convites excluídos em massa por {current_user.email}")
    return BulkDeleteResponse(deleted_count=len(deleted_ids), deleted_ids=deleted_ids)

