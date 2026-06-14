import pytest
import psycopg2
from admin_repository import AdminRepository
from system_prompt_defaults import DEFAULT_INSTRUCTIONS

TEST_URL = "postgresql://localhost:5432/postgres"


def _clean_admin_tables() -> None:
    conn = psycopg2.connect(TEST_URL)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM admin_credentials")
        cur.execute("DELETE FROM admin_mcp_servers")
        cur.execute("DELETE FROM admin_skills")
        cur.execute("DELETE FROM admin_personas")
        cur.execute("DELETE FROM admin_agent_instances")
        cur.execute("DELETE FROM admin_system_prompts")
    conn.commit()
    conn.close()


@pytest.fixture
def repo():
    r = AdminRepository(TEST_URL)
    # clean slate before each test
    _clean_admin_tables()
    return r


def test_credentials_empty_initially(repo):
    assert repo.get_credentials() is None


def test_upsert_and_get_credentials(repo):
    repo.upsert_credentials("AKID", "SECRET", "us-east-1", "kubeconfig: {}")
    creds = repo.get_credentials()
    assert creds["aws_access_key_id"] == "AKID"
    assert creds["aws_secret_access_key"] == "SECRET"
    assert creds["kubeconfig"] == "kubeconfig: {}"


def test_upsert_credentials_twice_keeps_one_row(repo):
    repo.upsert_credentials("A", "B", "us-east-1", None)
    repo.upsert_credentials("C", "D", "us-west-2", None)
    assert repo.get_credentials()["aws_access_key_id"] == "C"


def test_mcp_servers_empty_initially(repo):
    assert repo.get_mcp_servers() == []


def test_upsert_and_get_mcp_server(repo):
    repo.upsert_mcp_server(1, "my-server", {"url": "http://localhost:3001"})
    servers = repo.get_mcp_servers()
    assert len(servers) == 1
    assert servers[0]["name"] == "my-server"
    assert servers[0]["config"]["url"] == "http://localhost:3001"


def test_delete_mcp_server(repo):
    repo.upsert_mcp_server(2, "srv", {"url": "http://x"})
    assert repo.delete_mcp_server(2) is True
    assert repo.get_mcp_servers() == []


def test_delete_nonexistent_mcp_server(repo):
    assert repo.delete_mcp_server(3) is False


def test_save_and_list_skills(repo):
    skill_id = repo.save_skill("tool.py", "def tool(): pass")
    skills = repo.get_skills()
    assert len(skills) == 1
    assert skills[0]["filename"] == "tool.py"
    assert str(skills[0]["id"]) == skill_id


def test_delete_skill(repo):
    skill_id = repo.save_skill("x.py", "pass")
    assert repo.delete_skill(skill_id) is True
    assert repo.get_skills() == []


def test_delete_nonexistent_skill(repo):
    assert repo.delete_skill("00000000-0000-0000-0000-000000000000") is False


def test_create_and_list_personas(repo):
    skill_id = repo.save_skill("s.py", "pass")
    persona = repo.create_persona("DevOps", [skill_id])
    assert persona["name"] == "DevOps"
    assert skill_id in persona["skill_ids"]
    personas = repo.get_personas()
    assert len(personas) == 1


def test_update_persona(repo):
    persona = repo.create_persona("Eng", [])
    updated = repo.update_persona(str(persona["id"]), "SRE", [])
    assert updated["name"] == "SRE"


def test_delete_persona(repo):
    persona = repo.create_persona("Temp", [])
    assert repo.delete_persona(str(persona["id"])) is True
    assert repo.get_personas() == []


def test_persona_name_must_be_unique(repo):
    repo.create_persona("Unique", [])
    with pytest.raises(Exception):
        repo.create_persona("Unique", [])


def test_repository_seeds_default_kubernetes_agent_prompt():
    _clean_admin_tables()
    repo = AdminRepository(TEST_URL)

    prompts = repo.list_system_prompts()
    kubernetes_prompts = [p for p in prompts if p["name"] == "kubernetes_agent"]
    generic_prompts = [p for p in prompts if p["name"] == "default_agent"]

    assert len(kubernetes_prompts) == 1
    assert kubernetes_prompts[0]["instructions"] == DEFAULT_INSTRUCTIONS
    assert kubernetes_prompts[0]["is_active"] is True
    assert len(generic_prompts) == 1
    assert "general-purpose AI assistant" in generic_prompts[0]["instructions"]
    assert generic_prompts[0]["is_active"] is False
    assert repo.get_active_system_prompt() == DEFAULT_INSTRUCTIONS


def test_get_system_prompt_instructions_returns_prompt_text(repo):
    prompt = repo.create_system_prompt("custom_prompt", "custom instructions")

    assert repo.get_system_prompt_instructions(str(prompt["id"])) == "custom instructions"
    assert repo.get_system_prompt_instructions("00000000-0000-0000-0000-000000000000") is None


# ── Agent Instances ────────────────────────────────────────────────────────

def test_agent_instances_empty_initially(repo):
    assert repo.get_agent_instances("my-agent") == []


def test_create_and_list_agent_instances(repo):
    inst = repo.create_agent_instance("my-agent", "Support", None, [1, 2])
    assert inst["instance_name"] == "Support"
    assert inst["mcp_positions"] == [1, 2]
    assert inst["persona_id"] is None
    instances = repo.get_agent_instances("my-agent")
    assert len(instances) == 1


def test_create_agent_instance_with_persona(repo):
    persona = repo.create_persona("DevOps", [])
    inst = repo.create_agent_instance("my-agent", "Sales", str(persona["id"]), [3])
    assert str(inst["persona_id"]) == str(persona["id"])


def test_create_agent_instance_duplicate_name_raises(repo):
    repo.create_agent_instance("my-agent", "Support", None, [])
    with pytest.raises(Exception):
        repo.create_agent_instance("my-agent", "Support", None, [])


def test_update_agent_instance(repo):
    inst = repo.create_agent_instance("my-agent", "Support", None, [1])
    updated = repo.update_agent_instance(str(inst["id"]), "Sales", None, [2, 3])
    assert updated["instance_name"] == "Sales"
    assert updated["mcp_positions"] == [2, 3]


def test_update_nonexistent_agent_instance_returns_none(repo):
    result = repo.update_agent_instance(
        "00000000-0000-0000-0000-000000000000", "X", None, []
    )
    assert result is None


def test_delete_agent_instance(repo):
    inst = repo.create_agent_instance("my-agent", "Support", None, [])
    assert repo.delete_agent_instance(str(inst["id"])) is True
    assert repo.get_agent_instances("my-agent") == []


def test_delete_nonexistent_agent_instance(repo):
    assert repo.delete_agent_instance("00000000-0000-0000-0000-000000000000") is False


def test_get_instances_only_returns_matching_agent(repo):
    repo.create_agent_instance("agent-a", "Inst1", None, [])
    repo.create_agent_instance("agent-b", "Inst2", None, [])
    assert len(repo.get_agent_instances("agent-a")) == 1
    assert len(repo.get_agent_instances("agent-b")) == 1


# ── API-level tests ────────────────────────────────────────────────────────

import io
from fastapi.testclient import TestClient
from main import app

http = TestClient(app)


@pytest.fixture(autouse=True)
def clean_tables():
    _clean_admin_tables()
    yield


def test_get_credentials_initially_null():
    response = http.get("/admin/credentials")
    assert response.status_code == 200
    assert response.json() is None


def test_save_and_get_credentials_via_api():
    http.post("/admin/credentials", json={
        "aws_access_key_id": "AKID",
        "aws_secret_access_key": "SECRET",
        "aws_region": "us-east-1",
    })
    response = http.get("/admin/credentials")
    data = response.json()
    assert data["aws_access_key_id"] == "AKID"
    assert data["aws_secret_access_key"] == "***"


def test_save_mcp_server_invalid_position():
    response = http.post("/admin/mcp-servers/6", json={"name": "x", "config": {}})
    assert response.status_code == 422


def test_save_and_list_mcp_servers_via_api():
    http.post("/admin/mcp-servers/1", json={"name": "srv", "config": {"url": "http://x"}})
    response = http.get("/admin/mcp-servers")
    servers = response.json()
    assert any(s["name"] == "srv" for s in servers)


def test_upload_and_list_skills_via_api():
    file_content = b"def my_tool(): pass"
    response = http.post(
        "/admin/skills",
        files={"file": ("tool.py", io.BytesIO(file_content), "text/plain")},
    )
    assert response.status_code == 200
    skill = response.json()
    assert skill["filename"] == "tool.py"

    skills = http.get("/admin/skills").json()
    assert any(s["id"] == skill["id"] for s in skills)


def test_delete_skill_via_api():
    file_content = b"pass"
    upload = http.post(
        "/admin/skills",
        files={"file": ("del.py", io.BytesIO(file_content), "text/plain")},
    )
    skill_id = upload.json()["id"]
    response = http.delete(f"/admin/skills/{skill_id}")
    assert response.status_code == 200


def test_create_and_list_personas_via_api():
    response = http.post("/admin/personas", json={"name": "TestPersona", "skill_ids": []})
    assert response.status_code == 201
    persona = response.json()
    assert persona["name"] == "TestPersona"

    personas = http.get("/admin/personas").json()
    assert any(p["id"] == persona["id"] for p in personas)


def test_duplicate_persona_name_returns_409():
    http.post("/admin/personas", json={"name": "DupTest", "skill_ids": []})
    response = http.post("/admin/personas", json={"name": "DupTest", "skill_ids": []})
    assert response.status_code == 409


def test_update_persona_via_api():
    create = http.post("/admin/personas", json={"name": "OldName", "skill_ids": []})
    persona_id = create.json()["id"]
    response = http.put(f"/admin/personas/{persona_id}", json={"name": "NewName", "skill_ids": []})
    assert response.json()["name"] == "NewName"


def test_delete_persona_via_api():
    create = http.post("/admin/personas", json={"name": "ToDelete", "skill_ids": []})
    persona_id = create.json()["id"]
    response = http.delete(f"/admin/personas/{persona_id}")
    assert response.status_code == 200


# ── Agent Instances API ────────────────────────────────────────────────────

def test_list_agent_instances_empty():
    response = http.get("/admin/agent-instances?agent_name=my-agent")
    assert response.status_code == 200
    assert response.json() == []


def test_create_and_list_agent_instances_via_api():
    response = http.post("/admin/agent-instances", json={
        "agent_name": "my-agent",
        "instance_name": "Support",
        "mcp_positions": [1, 2],
    })
    assert response.status_code == 201
    inst = response.json()
    assert inst["instance_name"] == "Support"
    assert inst["mcp_positions"] == [1, 2]
    assert inst["persona_id"] is None

    listed = http.get("/admin/agent-instances?agent_name=my-agent").json()
    assert len(listed) == 1
    assert listed[0]["id"] == inst["id"]


def test_create_duplicate_instance_returns_409():
    http.post("/admin/agent-instances", json={
        "agent_name": "my-agent", "instance_name": "Support", "mcp_positions": [],
    })
    response = http.post("/admin/agent-instances", json={
        "agent_name": "my-agent", "instance_name": "Support", "mcp_positions": [],
    })
    assert response.status_code == 409


def test_update_agent_instance_via_api():
    inst = http.post("/admin/agent-instances", json={
        "agent_name": "my-agent", "instance_name": "Support", "mcp_positions": [1],
    }).json()
    response = http.put(f"/admin/agent-instances/{inst['id']}", json={
        "instance_name": "Sales",
        "mcp_positions": [2, 3],
    })
    assert response.status_code == 200
    assert response.json()["instance_name"] == "Sales"


def test_update_nonexistent_instance_returns_404():
    response = http.put(
        "/admin/agent-instances/00000000-0000-0000-0000-000000000000",
        json={"instance_name": "X", "mcp_positions": []},
    )
    assert response.status_code == 404


def test_delete_agent_instance_via_api():
    inst = http.post("/admin/agent-instances", json={
        "agent_name": "my-agent", "instance_name": "Support", "mcp_positions": [],
    }).json()
    response = http.delete(f"/admin/agent-instances/{inst['id']}")
    assert response.status_code == 200
    assert http.get("/admin/agent-instances?agent_name=my-agent").json() == []


def test_delete_nonexistent_instance_returns_404():
    response = http.delete("/admin/agent-instances/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


# ── get_all_agent_instances ────────────────────────────────────────────────

def test_get_all_agent_instances_empty(repo):
    assert repo.get_all_agent_instances() == []


def test_get_all_agent_instances_returns_all(repo):
    repo.create_agent_instance("agent-a", "inst-1", None, [])
    repo.create_agent_instance("agent-b", "inst-2", None, [])
    rows = repo.get_all_agent_instances()
    names = [r["instance_name"] for r in rows]
    assert "inst-1" in names
    assert "inst-2" in names


def test_get_all_agent_instances_sorted(repo):
    repo.create_agent_instance("zebra", "z-inst", None, [])
    repo.create_agent_instance("alpha", "a-inst", None, [])
    rows = repo.get_all_agent_instances()
    agent_names = [r["agent_name"] for r in rows]
    assert agent_names == sorted(agent_names)


# ── get_agent_instance ────────────────────────────────────────────────────

def test_get_agent_instance_returns_none_for_unknown(repo):
    import uuid
    assert repo.get_agent_instance(str(uuid.uuid4())) is None


def test_get_agent_instance_returns_row(repo):
    created = repo.create_agent_instance("agent-a", "my-inst", None, [1, 2])
    fetched = repo.get_agent_instance(str(created["id"]))
    assert fetched is not None
    assert fetched["instance_name"] == "my-inst"
    assert fetched["mcp_positions"] == [1, 2]


# ── get_persona ───────────────────────────────────────────────────────────

def test_get_persona_returns_none_for_unknown(repo):
    import uuid
    assert repo.get_persona(str(uuid.uuid4())) is None


def test_get_persona_returns_row(repo):
    created = repo.create_persona("My Persona", ["skill-1"])
    fetched = repo.get_persona(str(created["id"]))
    assert fetched is not None
    assert fetched["name"] == "My Persona"
    assert fetched["skill_ids"] == ["skill-1"]


# ── get_skill_content ─────────────────────────────────────────────────────

def test_get_skill_content_returns_none_for_unknown(repo):
    import uuid
    assert repo.get_skill_content(str(uuid.uuid4())) is None


def test_get_skill_content_returns_filename_and_content(repo):
    skill_id = repo.save_skill("my-skill.md", "# My Skill\nDo things.")
    result = repo.get_skill_content(skill_id)
    assert result is not None
    filename, content = result
    assert filename == "my-skill.md"
    assert content == "# My Skill\nDo things."
