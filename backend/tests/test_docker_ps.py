from app.routers.servers import parse_docker_ps


def test_parse_docker_ps_basic():
    out = "web-1\tnginx:1.27\tUp 3 days\napi\tmyrepo/api:latest\tUp 2 hours (healthy)"
    items = parse_docker_ps(out)
    assert items == [
        {"name": "web-1", "image": "nginx:1.27", "status": "Up 3 days"},
        {"name": "api", "image": "myrepo/api:latest", "status": "Up 2 hours (healthy)"},
    ]


def test_parse_docker_ps_malformed_line():
    items = parse_docker_ps("only-name\n\n")
    assert items == [{"name": "only-name", "image": "", "status": ""}]


def test_parse_docker_ps_empty():
    assert parse_docker_ps("") == []
