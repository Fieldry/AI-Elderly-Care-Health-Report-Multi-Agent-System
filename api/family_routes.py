"""
认证和家属端 API 路由
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, Dict, List
import sys
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

from auth_manager import AuthManager
from family_data_manager import FamilyDataManager

# 初始化管理器
auth_manager = AuthManager()
family_manager = FamilyDataManager()

# 创建路由
auth_router = APIRouter(prefix="/auth", tags=["认证"])
family_router = APIRouter(prefix="/family", tags=["家属端"])


# ==================== 数据模型 ====================

class RegisterRequest(BaseModel):
    """注册请求"""
    user_type: str  # elderly / family
    name: str
    phone: str
    password: str
    elderly_id: Optional[str] = None
    relation: Optional[str] = None


class LoginRequest(BaseModel):
    """登录请求"""
    phone: str
    password: str


class UpdateProfileRequest(BaseModel):
    """更新档案请求"""
    updates: Dict


class GenerateReportRequest(BaseModel):
    """生成报告请求"""
    report_data: Dict
    completion_rate: float


# ==================== 认证相关 API ====================

@auth_router.post("/register")
async def register(request: RegisterRequest):
    """用户注册"""
    success, msg, user_id = auth_manager.register_user(
        user_type=request.user_type,
        name=request.name,
        phone=request.phone,
        password=request.password,
        elderly_id=request.elderly_id,
        relation=request.relation
    )

    if not success:
        raise HTTPException(status_code=400, detail=msg)

    return {
        "success": True,
        "message": msg,
        "user_id": user_id
    }


@auth_router.post("/login")
async def login(request: LoginRequest):
    """用户登录"""
    success, msg, user_info = auth_manager.login(request.phone, request.password)

    if not success:
        raise HTTPException(status_code=401, detail=msg)

    return {
        "success": True,
        "message": msg,
        "data": user_info
    }


@auth_router.get("/me")
async def get_current_user(authorization: str = Header(None)):
    """获取当前用户信息"""
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少认证令牌")

    # 提取 token（Bearer token 格式）
    try:
        token = authorization.split(" ")[1]
    except IndexError:
        raise HTTPException(status_code=401, detail="无效的认证令牌格式")

    valid, payload = auth_manager.verify_token(token)
    if not valid:
        raise HTTPException(status_code=401, detail="令牌已过期或无效")

    user_info = auth_manager.get_user_info(payload["user_id"])
    if not user_info:
        raise HTTPException(status_code=404, detail="用户不存在")

    return {
        "success": True,
        "data": user_info
    }


# ==================== 家属端 API ====================

def verify_family_token(authorization: str = Header(None)) -> Dict:
    """验证家属 token 的依赖"""
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少认证令牌")

    try:
        token = authorization.split(" ")[1]
    except IndexError:
        raise HTTPException(status_code=401, detail="无效的认证令牌格式")

    valid, payload = auth_manager.verify_token(token)
    if not valid:
        raise HTTPException(status_code=401, detail="令牌已过期或无效")

    if payload.get("user_type") != "family":
        raise HTTPException(status_code=403, detail="只有家属可以访问此接口")

    return payload


@family_router.get("/elderly-list")
async def get_elderly_list(payload: Dict = Depends(verify_family_token)):
    """获取家属关联的老年人列表"""
    family_id = payload["user_id"]
    elderly_list = auth_manager.get_family_elderly_list(family_id)

    return {
        "success": True,
        "data": elderly_list
    }


@family_router.get("/elderly/{elderly_id}/profile")
async def get_elderly_profile(
    elderly_id: str,
    payload: Dict = Depends(verify_family_token)
):
    """获取老年人完整档案"""
    family_id = payload["user_id"]

    # 检查权限
    if not auth_manager.check_family_access(family_id, elderly_id):
        raise HTTPException(status_code=403, detail="无权访问该老年人信息")

    profile = family_manager.get_elderly_profile(elderly_id)
    if not profile:
        raise HTTPException(status_code=404, detail="档案不存在")

    return {
        "success": True,
        "data": profile
    }


@family_router.get("/elderly/{elderly_id}/completion-rate")
async def get_completion_rate(
    elderly_id: str,
    payload: Dict = Depends(verify_family_token)
):
    """获取完整度"""
    family_id = payload["user_id"]

    if not auth_manager.check_family_access(family_id, elderly_id):
        raise HTTPException(status_code=403, detail="无权访问该老年人信息")

    profile = family_manager.get_elderly_profile(elderly_id)
    if not profile:
        raise HTTPException(status_code=404, detail="档案不存在")

    missing = family_manager.get_missing_fields(elderly_id)

    return {
        "success": True,
        "data": {
            "completion_rate": profile["completion_rate"],
            "missing_fields": missing
        }
    }


@family_router.put("/elderly/{elderly_id}/profile")
async def update_elderly_profile(
    elderly_id: str,
    request: UpdateProfileRequest,
    payload: Dict = Depends(verify_family_token)
):
    """更新老年人档案"""
    family_id = payload["user_id"]

    if not auth_manager.check_family_access(family_id, elderly_id):
        raise HTTPException(status_code=403, detail="无权访问该老年人信息")

    success, msg = family_manager.update_elderly_profile(
        elderly_id=elderly_id,
        editor_id=family_id,
        editor_type="family",
        updates=request.updates
    )

    if not success:
        raise HTTPException(status_code=400, detail=msg)

    return {
        "success": True,
        "message": msg
    }


@family_router.get("/elderly/{elderly_id}/edit-log")
async def get_edit_log(
    elderly_id: str,
    limit: int = 100,
    payload: Dict = Depends(verify_family_token)
):
    """获取修改日志"""
    family_id = payload["user_id"]

    if not auth_manager.check_family_access(family_id, elderly_id):
        raise HTTPException(status_code=403, detail="无权访问该老年人信息")

    logs = family_manager.get_edit_log(elderly_id, limit)

    return {
        "success": True,
        "data": logs
    }


@family_router.get("/elderly/{elderly_id}/reports")
async def get_report_versions(
    elderly_id: str,
    payload: Dict = Depends(verify_family_token)
):
    """获取所有报告版本"""
    family_id = payload["user_id"]

    if not auth_manager.check_family_access(family_id, elderly_id):
        raise HTTPException(status_code=403, detail="无权访问该老年人信息")

    versions = family_manager.get_report_versions(elderly_id)

    return {
        "success": True,
        "data": versions
    }


@family_router.post("/elderly/{elderly_id}/generate-report")
async def generate_report(
    elderly_id: str,
    request: GenerateReportRequest,
    payload: Dict = Depends(verify_family_token)
):
    """生成新报告"""
    family_id = payload["user_id"]

    if not auth_manager.check_family_access(family_id, elderly_id):
        raise HTTPException(status_code=403, detail="无权访问该老年人信息")

    # 检查完整度
    if request.completion_rate < 0.5:
        raise HTTPException(
            status_code=400,
            detail="信息不足（完整度 < 50%），建议先补全更多信息"
        )

    success, msg, version_id = family_manager.generate_report_version(
        elderly_id=elderly_id,
        report_data=request.report_data,
        completion_rate=request.completion_rate,
        generated_by=family_id,
        generated_by_type="family"
    )

    if not success:
        raise HTTPException(status_code=400, detail=msg)

    return {
        "success": True,
        "message": msg,
        "version_id": version_id
    }


@family_router.get("/elderly/{elderly_id}/reports/{version_id}")
async def get_report_version(
    elderly_id: str,
    version_id: str,
    payload: Dict = Depends(verify_family_token)
):
    """获取特定版本的报告"""
    family_id = payload["user_id"]

    if not auth_manager.check_family_access(family_id, elderly_id):
        raise HTTPException(status_code=403, detail="无权访问该老年人信息")

    report = family_manager.get_report_version(version_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告版本不存在")

    return {
        "success": True,
        "data": report
    }


@family_router.delete("/elderly/{elderly_id}/reports/{version_id}")
async def delete_report_version(
    elderly_id: str,
    version_id: str,
    payload: Dict = Depends(verify_family_token)
):
    """删除报告版本"""
    family_id = payload["user_id"]

    if not auth_manager.check_family_access(family_id, elderly_id):
        raise HTTPException(status_code=403, detail="无权访问该老年人信息")

    success, msg = family_manager.delete_report_version(version_id)

    if not success:
        raise HTTPException(status_code=400, detail=msg)

    return {
        "success": True,
        "message": msg
    }


@family_router.get("/elderly/{elderly_id}/reports/{version_id_1}/compare/{version_id_2}")
async def compare_reports(
    elderly_id: str,
    version_id_1: str,
    version_id_2: str,
    payload: Dict = Depends(verify_family_token)
):
    """对比两个报告版本"""
    family_id = payload["user_id"]

    if not auth_manager.check_family_access(family_id, elderly_id):
        raise HTTPException(status_code=403, detail="无权访问该老年人信息")

    comparison = family_manager.compare_report_versions(version_id_1, version_id_2)
    if not comparison:
        raise HTTPException(status_code=404, detail="报告版本不存在")

    return {
        "success": True,
        "data": comparison
    }
