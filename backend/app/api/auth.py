import re
import secrets
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_password, hash_password, create_access_token
from app.models.user import User, UserInvite, EmailVerificationCode, PasswordResetToken
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserResponse,
    InviteValidateResponse,
    RegisterInviteRequest,
    SendVerificationCodeRequest,
    SendVerificationCodeResponse,
    ValidateResetTokenResponse,
    ResetPasswordRequest,
)
from app.api.deps import get_current_user
from app.core.rate_limit import rate_limit
from app.services.brevo import send_verification_code_email

logger = logging.getLogger("projetovturb.auth")
router = APIRouter(prefix="/auth", tags=["Autenticação"])

def validate_strong_password(password: str) -> None:
    """Valida requisitos de senha forte: 12+ caracteres, maiúscula, minúscula, número e caractere especial."""
    if len(password) < 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha deve conter no mínimo 12 caracteres."
        )
    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha deve conter pelo menos uma letra maiúscula."
        )
    if not re.search(r"[a-z]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha deve conter pelo menos uma letra minúscula."
        )
    if not re.search(r"[0-9]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha deve conter pelo menos um número."
        )
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?/~`]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha deve conter pelo menos um caractere especial (ex: !@#$%^&*)."
        )

def resolve_display_name(user: User, is_super_admin: bool) -> str:
    """Retorna o nome explícito ou formata o nome a partir do e-mail."""
    if user.name and user.name.strip():
        return user.name.strip()
    if is_super_admin:
        return "Super Admin"
    username = user.email.split("@")[0]
    cleaned = username.replace(".", " ").replace("_", " ").replace("-", " ")
    parts = [w.capitalize() for w in cleaned.split()]
    return " ".join(parts) or "Usuário"

@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit("login", 10))])
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Autentica o usuário pelo e-mail e senha com hash Argon2id e gera JWT de 24h."""
    email_clean = payload.email.strip().lower()
    user = db.query(User).filter(User.email.ilike(email_clean)).first()

    if not user:
        logger.warning(f"Tentativa de login com e-mail inexistente: {email_clean}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos."
        )

    if not verify_password(payload.password, user.password_hash):
        logger.warning(f"Tentativa de login com senha incorreta para: {email_clean}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos."
        )

    official_email = settings.SUPER_ADMIN_EMAIL.strip().lower()
    is_super = (
        user.email.strip().lower() == official_email or
        bool(user.is_super_admin) or
        user.role == "super_admin"
    )
    if is_super:
        user.is_super_admin = True
        user.role = "super_admin"

    access_token = create_access_token(data={
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "is_super_admin": user.is_super_admin
    })

    logger.info(f"Login bem-sucedido para o usuário: {user.email}")
    user_resp = UserResponse.model_validate(user)
    user_resp.name = resolve_display_name(user, user.is_super_admin)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_resp
    )

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Retorna os dados do usuário autenticado a partir do token JWT."""
    official_email = settings.SUPER_ADMIN_EMAIL.strip().lower()
    if (
        current_user.email.strip().lower() == official_email or
        bool(current_user.is_super_admin) or
        current_user.role == "super_admin"
    ):
        current_user.is_super_admin = True
        current_user.role = "super_admin"
    resp = UserResponse.model_validate(current_user)
    resp.name = resolve_display_name(current_user, current_user.is_super_admin)
    return resp

@router.get("/invite/{token}", response_model=InviteValidateResponse, dependencies=[Depends(rate_limit("invite", 30))])
def validate_invite(token: str, db: Session = Depends(get_db)):
    """Valida publicamente se o link de convite é válido e não expirou."""
    invite = db.query(UserInvite).filter(UserInvite.token == token.strip()).first()
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link de convite inválido ou não encontrado."
        )

    if invite.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este link de convite já foi utilizado."
        )

    now_utc = datetime.now(timezone.utc)
    if invite.expires_at < now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este link de convite expirou."
        )

    return InviteValidateResponse(
        valid=True,
        role=invite.role,
        expires_at=invite.expires_at
    )

@router.post("/send-verification-code", response_model=SendVerificationCodeResponse, dependencies=[Depends(rate_limit("send-code", 5))])
def send_verification_code(payload: SendVerificationCodeRequest, db: Session = Depends(get_db)):
    """Gera e envia código de 6 dígitos para o e-mail via Brevo para ativação de conta."""
    token_clean = payload.token.strip()
    invite = db.query(UserInvite).filter(UserInvite.token == token_clean).first()
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link de convite inválido ou inexistente."
        )

    if invite.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este link de convite já foi utilizado."
        )

    now_utc = datetime.now(timezone.utc)
    if invite.expires_at < now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este link de convite expirou."
        )

    email_clean = payload.email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe um endereço de e-mail válido."
        )

    # Requisito 6: Bloqueia criação com e-mail já existente
    existing = db.query(User).filter(func.lower(User.email) == email_clean).first()
    if existing:
        logger.warning(f"Tentativa de cadastro com e-mail já em uso: {email_clean}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este e-mail já está cadastrado no sistema. Por favor, utilize outro e-mail ou faça login."
        )

    # Gera código aleatório de 6 dígitos numéricos
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    expires_at = now_utc + timedelta(minutes=15)

    verification_entry = EmailVerificationCode(
        email=email_clean,
        token=token_clean,
        code=code,
        expires_at=expires_at,
        is_verified=False,
    )
    db.add(verification_entry)
    db.commit()

    # Dispara e-mail via serviço Brevo
    send_verification_code_email(email_clean, code, payload.name)

    return SendVerificationCodeResponse(
        success=True,
        message=f"Código de verificação enviado para {email_clean}."
    )

@router.post("/register-invite", response_model=TokenResponse, dependencies=[Depends(rate_limit("register", 10))])
def register_via_invite(payload: RegisterInviteRequest, db: Session = Depends(get_db)):
    """Cadastra um novo usuário via link de convite com validação rigorosa de código Brevo e senha forte."""
    token_clean = payload.token.strip()
    invite = db.query(UserInvite).filter(UserInvite.token == token_clean).first()
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link de convite inválido ou inexistente."
        )

    if invite.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este link de convite já foi utilizado."
        )

    now_utc = datetime.now(timezone.utc)
    if invite.expires_at < now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este link de convite expirou."
        )

    email_clean = payload.email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe um endereço de e-mail válido."
        )

    # Requisito 6: Bloqueia criação com e-mail já existente
    existing = db.query(User).filter(func.lower(User.email) == email_clean).first()
    if existing:
        logger.warning(f"Tentativa de cadastro com e-mail duplicado: {email_clean}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este e-mail já está cadastrado no sistema. Por favor, utilize outro e-mail ou faça login."
        )

    # Validação estrita da senha forte
    validate_strong_password(payload.password)

    # Requisito 5: Validação do código de 6 dígitos enviado por e-mail
    code_clean = payload.code.strip()
    if not code_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe o código de verificação de 6 dígitos recebido por e-mail."
        )

    code_entry = db.query(EmailVerificationCode).filter(
        EmailVerificationCode.email == email_clean,
        EmailVerificationCode.token == token_clean,
        EmailVerificationCode.code == code_clean,
        EmailVerificationCode.is_verified == False
    ).order_by(EmailVerificationCode.created_at.desc()).first()

    if not code_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código de verificação incorreto ou inválido."
        )

    if code_entry.expires_at < now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O código de verificação expirou. Por favor, solicite um novo código."
        )

    # Marca código como verificado
    code_entry.is_verified = True

    # Cria o usuário com o perfil do convite
    assigned_role = invite.role.lower()
    if assigned_role not in ["admin", "user"]:
        assigned_role = "user"

    user_name = payload.name.strip() if payload.name and payload.name.strip() else None
    new_user = User(
        email=email_clean,
        name=user_name,
        password_hash=hash_password(payload.password),
        role=assigned_role,
        is_super_admin=False,
    )
    db.add(new_user)

    # Marca o convite como utilizado
    invite.is_used = True
    invite.used_by_email = email_clean

    db.commit()
    db.refresh(new_user)

    logger.info(f"Usuário criado via convite validado por código: {email_clean} com função '{assigned_role}'")

    access_token = create_access_token(data={
        "sub": new_user.id,
        "email": new_user.email,
        "role": new_user.role,
        "is_super_admin": new_user.is_super_admin
    })

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user)
    )

@router.get("/validate-reset-token", response_model=ValidateResetTokenResponse, dependencies=[Depends(rate_limit("validate-reset", 30))])
def validate_reset_token(token: str, db: Session = Depends(get_db)):
    """Valida se um token de redefinição de senha existe, é válido e não expirou."""
    now = datetime.now(timezone.utc)
    token_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token,
        PasswordResetToken.is_used.is_(False),
        PasswordResetToken.expires_at > now
    ).first()

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link de redefinição de senha inválido ou expirado."
        )

    user = db.query(User).filter(User.id == token_record.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário associado a este token não foi encontrado."
        )

    return ValidateResetTokenResponse(
        valid=True,
        email=user.email,
        name=user.name
    )

@router.post("/reset-password", dependencies=[Depends(rate_limit("reset-password", 10))])
def execute_password_reset(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Aplica a nova senha informada pelo usuário através de um token de redefinição válido."""
    now = datetime.now(timezone.utc)
    token_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == payload.token,
        PasswordResetToken.is_used.is_(False),
        PasswordResetToken.expires_at > now
    ).first()

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link de redefinição de senha inválido ou expirado."
        )

    validate_strong_password(payload.password)

    user = db.query(User).filter(User.id == token_record.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário associado a este token não foi encontrado."
        )

    # Atualiza a senha com hash Argon2id
    user.password_hash = hash_password(payload.password)
    token_record.is_used = True
    db.commit()

    logger.info(f"Senha do usuário {user.email} redefinida com sucesso via token seguro.")
    return {
        "success": True,
        "message": "Sua senha foi redefinida com sucesso! Você já pode entrar com sua nova senha."
    }


