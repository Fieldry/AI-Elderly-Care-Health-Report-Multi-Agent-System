from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatStartResponse(BaseModel):
    userId: str
    sessionId: str
    welcomeMessage: str
    interaction: Optional[Dict[str, Any]] = None
    accessToken: Optional[str] = None
    userType: Optional[str] = None
    expiresAt: Optional[str] = None


class ChatMessageRequest(BaseModel):
    message: str = ""
    sessionId: str
    context: Optional[Dict[str, Any]] = None
    answer: Optional[Dict[str, Any]] = None


class ChatMessageResponse(BaseModel):
    message: str
    state: str
    progress: float
    completed: bool = False
    interaction: Optional[Dict[str, Any]] = None


class ChatProgressResponse(BaseModel):
    state: str
    progress: float
    completedGroups: List[str] = Field(default_factory=list)
    pendingGroups: List[str] = Field(default_factory=list)
    missingFields: Dict[str, List[str]] = Field(default_factory=dict)
    interaction: Optional[Dict[str, Any]] = None


class ChatHistoryMessage(BaseModel):
    role: str
    content: str
    timestamp: Optional[str] = None


class ReportGenerateRequest(BaseModel):
    profile: Dict[str, Any] = Field(default_factory=dict)
    sessionId: Optional[str] = None


class FamilyRegisterRequest(BaseModel):
    name: str
    phone: str
    password: str
    elderlyId: str
    relation: str = "家属"


class FamilyBindRequest(BaseModel):
    elderlyId: str
    relation: str = "家属"


class RiskItem(BaseModel):
    name: str
    level: str
    description: str
    timeframe: str


class RecommendationItem(BaseModel):
    id: str
    title: str
    description: str
    category: str
    completed: bool = False


class ReportData(BaseModel):
    summary: str
    healthPortrait: Dict[str, Any]
    riskFactors: Dict[str, List[RiskItem]]
    recommendations: Dict[str, List[RecommendationItem]]
    warmMessage: str = ""
    generatedAt: str


class ReportGenerateByElderlyResponse(BaseModel):
    reportId: str
    sessionId: str
    report: ReportData


class AgentStatusEvent(BaseModel):
    agent: str
    status: str
    message: Optional[str] = None


class LoginRequest(BaseModel):
    phone: str
    password: str
    role: str = "family"


class AuthResponse(BaseModel):
    token: str
    expires_at: str
    user_name: str
    role: str
    family_id: Optional[str] = None
    elderly_ids: List[str] = Field(default_factory=list)


class DoctorFollowupCreateRequest(BaseModel):
    visitType: str
    findings: str
    recommendations: List[str] = Field(default_factory=list)
    contactedFamily: bool = False
    arrangedRevisit: bool = False
    referred: bool = False
    nextFollowupAt: Optional[str] = None
    notes: str = ""


class DoctorManagementUpdateRequest(BaseModel):
    isKeyCase: Optional[bool] = None
    managementStatus: Optional[str] = None
    contactedFamily: Optional[bool] = None
    arrangedRevisit: Optional[bool] = None
    referred: Optional[bool] = None
    nextFollowupAt: Optional[str] = None


# ── 心理咨询 ──────────────────────────────────────────────


class CounselingSessionCreateResponse(BaseModel):
    sessionId: str
    createdAt: str


class CounselingMessageRequest(BaseModel):
    message: str


class CounselingMessageResponse(BaseModel):
    messageId: str
    role: str
    content: str
    createdAt: str


class CounselingSessionInfo(BaseModel):
    sessionId: str
    userId: str
    title: str
    status: str
    createdAt: str
    updatedAt: str
