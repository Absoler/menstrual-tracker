"""注册 / 登录 / 当前用户接口。"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import auth, db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterBody(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(body: RegisterBody):
    username = body.username.strip()
    with db.get_db() as conn:
        if conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone():
            raise HTTPException(status_code=409, detail="用户名已存在")
        password_hash = auth.hash_password(body.password)
        cur = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
    return {"token": auth.create_token(cur.lastrowid, username), "username": username}


@router.post("/login")
def login(body: LoginBody):
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username=?",
            (body.username.strip(),),
        ).fetchone()
    if row is None or not auth.verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"token": auth.create_token(row["id"], row["username"]), "username": row["username"]}


@router.get("/me")
def me(user: dict = Depends(auth.get_current_user)):
    return user
