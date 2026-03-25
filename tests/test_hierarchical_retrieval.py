from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR / "code"))

from knowledge_agent import KnowledgeAgent  # noqa: E402
from rag.agent import PageIndexRAGAgent  # noqa: E402


class FakeRAG:
    def __init__(self):
        self.doc_catalog = [
            {
                "doc_id": "doc_heart",
                "doc_name": "心血管照护指南.pdf",
                "doc_summary": "涵盖独居高龄老人心血管风险管理与居家应对。",
                "outline_nodes": [{"node_id": "node_heart", "title": "居家管理", "path": "居家管理", "summary": "紧急识别与就医"}],
            },
            {
                "doc_id": "doc_fall",
                "doc_name": "跌倒预防指南.pdf",
                "doc_summary": "涵盖夜间起身、地面湿滑和扶手安装等内容。",
                "outline_nodes": [{"node_id": "node_fall", "title": "环境改造", "path": "环境改造", "summary": "夜灯和扶手"}],
            },
        ]
        self.node_catalog = [
            {
                "node_id": "node_heart",
                "doc_id": "doc_heart",
                "doc_name": "心血管照护指南.pdf",
                "path": "居家管理 > 紧急识别",
                "summary": "胸痛、气短时及时呼救并建立就医通道。",
                "level": 2,
            },
            {
                "node_id": "node_fall",
                "doc_id": "doc_fall",
                "doc_name": "跌倒预防指南.pdf",
                "path": "环境改造 > 夜间照明",
                "summary": "卧室到卫生间安装夜灯并清理绊倒物。",
                "level": 2,
            },
        ]
        self.full_nodes = {
            "node_heart": {
                "node_id": "node_heart",
                "doc_id": "doc_heart",
                "doc_name": "心血管照护指南.pdf",
                "path": "居家管理 > 紧急识别",
                "title": "紧急识别",
                "summary": "胸痛、气短时及时呼救并建立就医通道。",
                "text": "当老年患者出现胸痛、明显气短时，应立即呼叫家属或急救，并预先准备固定就诊医院和联系人。",
            },
            "node_fall": {
                "node_id": "node_fall",
                "doc_id": "doc_fall",
                "doc_name": "跌倒预防指南.pdf",
                "path": "环境改造 > 夜间照明",
                "title": "夜间照明",
                "summary": "卧室到卫生间安装夜灯并清理绊倒物。",
                "text": "建议在卧室到卫生间路径安装感应夜灯，并移除地面水渍、电线和松动地毯，降低夜间跌倒风险。",
            },
        }

    def get_document_catalog(self):
        return self.doc_catalog

    def get_node_catalog(self, doc_ids=None, max_level=3, limit_per_doc=40):
        allowed = set(doc_ids or [])
        return [node for node in self.node_catalog if not allowed or node["doc_id"] in allowed]

    def get_nodes_by_ids(self, node_ids):
        return [self.full_nodes[node_id] for node_id in node_ids if node_id in self.full_nodes]

    def build_context(self, query, top_k=3):
        return {
            "query": query,
            "hits": [{"excerpt": "备用关键词检索结果", "text": "备用关键词检索结果"}],
            "context": "备用关键词检索结果",
        }


class ProfileStub:
    age = 87
    sex = "女"
    residence = "农村"
    living_arrangement = "独居"
    caregiver = "子女"
    medical_insurance = "新农合"
    coronary_heart_disease = "是"
    heart_failure = "否"
    arrhythmia = "否"
    hypertension = "否"
    diabetes = "否"
    stroke = "否"
    arthritis = "否"
    cancer = "否"
    hearing_impairment = "是"


class HierarchicalRetrievalTestCase(unittest.TestCase):
    def test_page_index_agent_backfills_document_and_node_catalog(self):
        payload = {
            "documents": [
                {
                    "doc_name": "测试指南.pdf",
                    "source_path": "/tmp/test.pdf",
                    "source_type": "pdf",
                    "structure": [],
                }
            ],
            "chunks": [
                {
                    "doc_name": "测试指南.pdf",
                    "source_path": "/tmp/test.pdf",
                    "source_type": "pdf",
                    "title": "居家安全",
                    "path": "居家安全",
                    "text": "建议安装夜灯和扶手。",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            index_path = Path(tmp_dir) / "index.json"
            index_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            agent = PageIndexRAGAgent(index_path=str(index_path))

            documents = agent.get_document_catalog()
            nodes = agent.get_node_catalog()

        self.assertEqual(len(documents), 1)
        self.assertEqual(len(nodes), 1)
        self.assertTrue(documents[0]["doc_summary"])
        self.assertTrue(nodes[0]["summary"])
        self.assertTrue(nodes[0]["node_id"])

    def test_knowledge_agent_returns_hierarchical_result(self):
        agent = KnowledgeAgent(FakeRAG())
        responses = iter(
            [
                {
                    "selected_docs": [
                        {"doc_id": "doc_heart", "reason": "覆盖心脏风险", "relevance_to_case": "心血管突发风险"},
                        {"doc_id": "doc_fall", "reason": "覆盖跌倒风险", "relevance_to_case": "夜间跌倒预防"},
                    ]
                },
                {
                    "selected_nodes": [
                        {"node_id": "node_heart", "reason": "含有紧急应对措施", "need": "胸痛气短时的家庭应对"},
                        {"node_id": "node_fall", "reason": "含有环境改造方法", "need": "夜间跌倒预防"},
                    ]
                },
                {
                    "evidence_cards": [
                        {
                            "need": "胸痛气短时的家庭应对",
                            "recommendation": "提前准备固定就诊医院和紧急联系人。",
                            "evidence_quote": "应立即呼叫家属或急救，并预先准备固定就诊医院和联系人。",
                            "node_id": "node_heart",
                            "applicability": "适合独居且存在心血管风险的老人。",
                        },
                        {
                            "need": "夜间跌倒预防",
                            "recommendation": "卧室到卫生间路径安装感应夜灯并清理绊倒物。",
                            "evidence_quote": "建议在卧室到卫生间路径安装感应夜灯，并移除地面水渍、电线和松动地毯。",
                            "node_id": "node_fall",
                            "applicability": "适合夜间起身风险较高的独居老人。",
                        },
                    ]
                },
            ]
        )
        agent._call_llm_json = lambda prompt, max_tokens=4096: next(responses)  # type: ignore[method-assign]

        result = agent.retrieve_comprehensive(
            ProfileStub(),
            status_result={"status_name": "需要部分协助", "status_description": "夜间活动不稳"},
            risk_result={
                "overall_risk_level": "高",
                "short_term_risks": [{"risk": "急性心血管事件", "severity": "高"}],
                "medium_term_risks": [{"risk": "跌倒及继发伤害", "severity": "中"}],
            },
            factor_result={"main_problems": ["独居", "听力障碍"], "changeable_factors": ["居家环境"]},
            top_k=3,
        )

        self.assertEqual(result["retrieval_mode"], "hierarchical_llm")
        self.assertEqual(len(result["selected_docs"]), 2)
        self.assertEqual(len(result["selected_nodes"]), 2)
        self.assertEqual(len(result["evidence_cards"]), 2)
        self.assertIn("结构化知识证据", result["combined_context"])

    def test_knowledge_agent_falls_back_when_llm_route_fails(self):
        agent = KnowledgeAgent(FakeRAG())
        agent._call_llm_json = lambda prompt, max_tokens=4096: (_ for _ in ()).throw(ValueError("bad json"))  # type: ignore[method-assign]

        result = agent.retrieve_comprehensive(
            ProfileStub(),
            status_result={"status_name": "需要部分协助", "status_description": "夜间活动不稳"},
            risk_result={"overall_risk_level": "高", "short_term_risks": [{"risk": "急性心血管事件", "severity": "高"}]},
            factor_result={"main_problems": ["独居"], "changeable_factors": []},
            top_k=2,
        )

        self.assertEqual(result["retrieval_mode"], "fallback_keyword")
        self.assertEqual(result["selected_docs"], [])
        self.assertEqual(result["selected_nodes"], [])
        self.assertIn("fallback_reason", result["retrieval_trace"])


if __name__ == "__main__":
    unittest.main()
