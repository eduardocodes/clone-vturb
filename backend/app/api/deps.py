from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

security_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Valida o token JWT do header Authorization e injeta o usuário autenticado."""
    raw_token = auth_header.credentials if auth_header and auth_header.credentials else None
    return _user_from_token(raw_token, db)


def get_current_user_allow_query_token(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Como get_current_user, mas aceita ?token= (só para links de download abertos pelo navegador)."""
    raw_token = auth_header.credentials if auth_header and auth_header.credentials else None
    if not raw_token:
        raw_token = request.query_params.get("token")
    return _user_from_token(raw_token, db)


def _user_from_token(raw_token: Optional[str], db: Session) -> User:
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária. Token não fornecido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(raw_token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado. Faça login novamente.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload["sub"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário associado ao token não foi encontrado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
