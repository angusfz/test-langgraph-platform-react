import asyncio
from typing import Any, Dict

import pytest

from react_agent import tools


def test_search_104_jobs_success(monkeypatch: pytest.MonkeyPatch) -> None:
    payload: Dict[str, Any] = {
        "status": 200,
        "data": {
            "query": {"page": 2},
            "list": [
                {
                    "jobName": "Python Engineer",
                    "custName": "Example Corp",
                    "jobAddrNoDesc": "台北市信義區",
                    "salaryDesc": "月薪 70,000-90,000 元",
                    "appearDate": "20251015",
                    "link": {"job": "//www.104.com.tw/job/8abcd"},
                    "descWithoutHighlight": "Develop backend services using Python.",
                }
            ],
            "totalCount": 123,
        },
    }

    async def fake_to_thread(func: Any, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return payload

    monkeypatch.setattr(tools.asyncio, "to_thread", fake_to_thread)

    result = asyncio.run(tools.search_104_jobs("Python page=2"))

    assert result is not None
    assert result["keyword"] == "Python"
    assert result["page"] == 2
    assert result["total_count"] == 123
    assert len(result["jobs"]) == 1
    assert result["jobs"][0]["job_url"] == "https://www.104.com.tw/job/8abcd"


def test_search_104_jobs_empty_keyword() -> None:
    assert asyncio.run(tools.search_104_jobs("   ")) is None


def test_search_104_jobs_request_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_to_thread(func: Any, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {}

    monkeypatch.setattr(tools.asyncio, "to_thread", fake_to_thread)

    assert asyncio.run(tools.search_104_jobs("Python")) is None
