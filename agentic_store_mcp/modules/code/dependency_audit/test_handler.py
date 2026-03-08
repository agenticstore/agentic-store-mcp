"""
Tests for dependency_audit — all ecosystems.
All network calls (PyPI, npm, Go proxy, Maven, OSV) are mocked.
"""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

_spec = importlib.util.spec_from_file_location("dependency_audit_handler", Path(__file__).parent / "handler.py")
h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)  # type: ignore[union-attr]
run = h.run

# ─── Helpers ──────────────────────────────────────────────────────────────────


def write(base: Path, name: str, content: str) -> Path:
    p = base / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


def no_vulns(name, version, ecosystem):
    return []


def mock_vuln(name, version, ecosystem):
    return [{"id": "CVE-TEST-001", "summary": "Test vuln", "severity": "HIGH", "url": ""}]


# ─── Python ───────────────────────────────────────────────────────────────────


def test_parse_requirements_exact_pin(tmp_path):
    write(tmp_path, "requirements.txt", "requests==2.28.0\nfastapi>=0.100.0\n")
    pkgs = h.parse_requirements_txt(tmp_path / "requirements.txt")
    req = next(p for p in pkgs if p["name"] == "requests")
    fast = next(p for p in pkgs if p["name"] == "fastapi")
    assert req["current_version"] == "2.28.0"
    assert fast["current_version"] is None


def test_parse_requirements_skips_vcs_and_flags(tmp_path):
    content = "git+https://github.com/org/repo.git\n-r other.txt\n-e .\nrequests==2.28.0\n"
    write(tmp_path, "requirements.txt", content)
    pkgs = h.parse_requirements_txt(tmp_path / "requirements.txt")
    assert len(pkgs) == 1 and pkgs[0]["name"] == "requests"


def test_parse_requirements_strips_extras(tmp_path):
    write(tmp_path, "requirements.txt", "requests[security]==2.28.0\n")
    pkgs = h.parse_requirements_txt(tmp_path / "requirements.txt")
    assert pkgs[0]["name"] == "requests"


def test_parse_pyproject_pep621(tmp_path):
    write(tmp_path, "pyproject.toml", '[project]\ndependencies = ["requests==2.28.0"]\n')
    pkgs = h.parse_pyproject_toml(tmp_path / "pyproject.toml")
    assert any(p["name"] == "requests" and p["current_version"] == "2.28.0" for p in pkgs)


def test_parse_pyproject_poetry_skips_python(tmp_path):
    write(tmp_path, "pyproject.toml", '[tool.poetry.dependencies]\npython = "^3.12"\nrequests = "^2.28.0"\n')
    pkgs = h.parse_pyproject_toml(tmp_path / "pyproject.toml")
    assert not any(p["name"] == "python" for p in pkgs)
    assert any(p["name"] == "requests" for p in pkgs)


# ─── JavaScript / npm ─────────────────────────────────────────────────────────


def test_parse_package_json_strips_semver_range(tmp_path):
    data = {"dependencies": {"axios": "^1.4.0", "react": "~18.2.0", "lodash": ">=4.17.0"}}
    write(tmp_path, "package.json", json.dumps(data))
    pkgs = h.parse_package_json(tmp_path / "package.json")
    assert next(p for p in pkgs if p["name"] == "axios")["current_version"] == "1.4.0"
    assert next(p for p in pkgs if p["name"] == "react")["current_version"] == "18.2.0"


def test_parse_package_json_includes_dev_deps(tmp_path):
    data = {"dependencies": {"react": "^18.0.0"}, "devDependencies": {"jest": "^29.0.0"}}
    write(tmp_path, "package.json", json.dumps(data))
    pkgs = h.parse_package_json(tmp_path / "package.json")
    assert any(p["name"] == "react" for p in pkgs)
    assert any(p["name"] == "jest" for p in pkgs)


def test_parse_package_json_skips_local_and_git(tmp_path):
    data = {"dependencies": {"mylib": "file:../mylib", "gitpkg": "git+https://github.com/x/y", "axios": "^1.4.0"}}
    write(tmp_path, "package.json", json.dumps(data))
    pkgs = h.parse_package_json(tmp_path / "package.json")
    names = [p["name"] for p in pkgs]
    assert "mylib" not in names and "gitpkg" not in names
    assert "axios" in names


# ─── Go ───────────────────────────────────────────────────────────────────────


def test_parse_go_mod_block_style(tmp_path):
    content = """\
module github.com/myorg/myapp

go 1.21

require (
    github.com/gin-gonic/gin v1.9.1
    github.com/stretchr/testify v1.8.4 // indirect
)
"""
    write(tmp_path, "go.mod", content)
    pkgs = h.parse_go_mod(tmp_path / "go.mod")
    names = [p["name"] for p in pkgs]
    assert "github.com/gin-gonic/gin" in names
    assert "github.com/stretchr/testify" in names
    # 'go' and 'module' directives should NOT be packages
    assert not any(p["name"] in ("go", "module") for p in pkgs)


def test_parse_go_mod_single_line_require(tmp_path):
    content = "module github.com/myorg/myapp\n\ngo 1.21\n\nrequire github.com/some/dep v0.1.0\n"
    write(tmp_path, "go.mod", content)
    pkgs = h.parse_go_mod(tmp_path / "go.mod")
    assert any(p["name"] == "github.com/some/dep" and p["current_version"] == "v0.1.0" for p in pkgs)


def test_parse_go_mod_ecosystem_is_go(tmp_path):
    write(tmp_path, "go.mod", "module x\n\nrequire github.com/foo/bar v1.0.0\n")
    pkgs = h.parse_go_mod(tmp_path / "go.mod")
    assert all(p["ecosystem"] == "Go" for p in pkgs)


def test_go_escape_uppercase():
    assert h._go_escape("github.com/BurntSushi/toml") == "github.com/!burnt!sushi/toml"


# ─── Java — Maven ─────────────────────────────────────────────────────────────


def test_parse_pom_xml_with_namespace(tmp_path):
    content = """\
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <dependencies>
    <dependency>
      <groupId>org.springframework</groupId>
      <artifactId>spring-core</artifactId>
      <version>5.3.29</version>
    </dependency>
  </dependencies>
</project>
"""
    write(tmp_path, "pom.xml", content)
    pkgs = h.parse_pom_xml(tmp_path / "pom.xml")
    assert any(p["name"] == "org.springframework:spring-core" and p["current_version"] == "5.3.29" for p in pkgs)


def test_parse_pom_xml_without_namespace(tmp_path):
    content = """\
<project>
  <dependencies>
    <dependency>
      <groupId>junit</groupId>
      <artifactId>junit</artifactId>
      <version>4.13.2</version>
    </dependency>
  </dependencies>
</project>
"""
    write(tmp_path, "pom.xml", content)
    pkgs = h.parse_pom_xml(tmp_path / "pom.xml")
    assert any(p["name"] == "junit:junit" for p in pkgs)


def test_parse_pom_xml_skips_property_version(tmp_path):
    content = """\
<project>
  <dependencies>
    <dependency>
      <groupId>org.springframework</groupId>
      <artifactId>spring-core</artifactId>
      <version>${spring.version}</version>
    </dependency>
  </dependencies>
</project>
"""
    write(tmp_path, "pom.xml", content)
    pkgs = h.parse_pom_xml(tmp_path / "pom.xml")
    pkg = pkgs[0]
    assert pkg["current_version"] is None  # placeholder stripped


def test_parse_pom_xml_invalid_raises(tmp_path):
    write(tmp_path, "pom.xml", "NOT XML ][")
    with pytest.raises(ValueError, match="Invalid XML"):
        h.parse_pom_xml(tmp_path / "pom.xml")


# ─── Java — Gradle ────────────────────────────────────────────────────────────


def test_parse_build_gradle_groovy(tmp_path):
    content = """\
dependencies {
    implementation 'org.springframework:spring-core:5.3.29'
    testImplementation "junit:junit:4.13.2"
    runtimeOnly 'com.google.guava:guava:32.1.3-jre'
}
"""
    write(tmp_path, "build.gradle", content)
    pkgs = h.parse_build_gradle(tmp_path / "build.gradle")
    names = [p["name"] for p in pkgs]
    assert "org.springframework:spring-core" in names
    assert "junit:junit" in names
    assert "com.google.guava:guava" in names


def test_parse_build_gradle_kts(tmp_path):
    content = """\
dependencies {
    implementation("org.springframework:spring-core:5.3.29")
    testImplementation("junit:junit:4.13.2")
}
"""
    write(tmp_path, "build.gradle.kts", content)
    pkgs = h.parse_build_gradle(tmp_path / "build.gradle.kts")
    assert any(p["name"] == "org.springframework:spring-core" for p in pkgs)


def test_parse_build_gradle_ecosystem_is_maven(tmp_path):
    write(tmp_path, "build.gradle", "dependencies { implementation 'g:a:1.0' }")
    pkgs = h.parse_build_gradle(tmp_path / "build.gradle")
    assert all(p["ecosystem"] == "Maven" for p in pkgs)


# ─── C++ — Conan ──────────────────────────────────────────────────────────────


def test_parse_conanfile_txt(tmp_path):
    content = "[requires]\nboost/1.83.0\nopenssl/3.1.2\nzlib/1.3\n\n[generators]\ncmake\n"
    write(tmp_path, "conanfile.txt", content)
    pkgs = h.parse_conanfile_txt(tmp_path / "conanfile.txt")
    names = [p["name"] for p in pkgs]
    assert "boost" in names and "openssl" in names and "zlib" in names
    assert next(p for p in pkgs if p["name"] == "boost")["current_version"] == "1.83.0"


def test_parse_conanfile_txt_skips_non_requires_sections(tmp_path):
    content = "[generators]\ncmake\n\n[requires]\nboost/1.83.0\n\n[options]\nboost:shared=True\n"
    write(tmp_path, "conanfile.txt", content)
    pkgs = h.parse_conanfile_txt(tmp_path / "conanfile.txt")
    assert all(p["name"] == "boost" for p in pkgs)


def test_parse_conanfile_py(tmp_path):
    content = 'class MyProject:\n    requires = "boost/1.83.0", "openssl/3.1.2"\n'
    write(tmp_path, "conanfile.py", content)
    pkgs = h.parse_conanfile_py(tmp_path / "conanfile.py")
    assert any(p["name"] == "boost" and p["current_version"] == "1.83.0" for p in pkgs)
    assert any(p["name"] == "openssl" for p in pkgs)


def test_parse_conanfile_ecosystem_is_conancenter(tmp_path):
    write(tmp_path, "conanfile.txt", "[requires]\nboost/1.83.0\n")
    pkgs = h.parse_conanfile_txt(tmp_path / "conanfile.txt")
    assert all(p["ecosystem"] == "ConanCenter" for p in pkgs)


# ─── C++ — vcpkg ──────────────────────────────────────────────────────────────


def test_parse_vcpkg_json_string_deps(tmp_path):
    data = {"name": "myproject", "dependencies": ["boost", "openssl", "zlib"]}
    write(tmp_path, "vcpkg.json", json.dumps(data))
    pkgs = h.parse_vcpkg_json(tmp_path / "vcpkg.json")
    names = [p["name"] for p in pkgs]
    assert "boost" in names and "openssl" in names


def test_parse_vcpkg_json_object_deps(tmp_path):
    data = {"dependencies": [{"name": "boost", "version>=": "1.83"}, {"name": "zlib"}]}
    write(tmp_path, "vcpkg.json", json.dumps(data))
    pkgs = h.parse_vcpkg_json(tmp_path / "vcpkg.json")
    boost = next(p for p in pkgs if p["name"] == "boost")
    assert boost["current_version"] == "1.83"


def test_parse_vcpkg_ecosystem_is_vcpkg(tmp_path):
    write(tmp_path, "vcpkg.json", json.dumps({"dependencies": ["boost"]}))
    pkgs = h.parse_vcpkg_json(tmp_path / "vcpkg.json")
    assert all(p["ecosystem"] == "vcpkg" for p in pkgs)


def test_vcpkg_has_note_in_output(tmp_path):
    write(tmp_path, "vcpkg.json", json.dumps({"dependencies": ["boost"]}))
    with (
        patch.object(h, "get_osv_vulnerabilities", side_effect=no_vulns),
    ):
        result = run({"path": str(tmp_path)})
    cpp = result["result"]["findings"]["cpp"]
    assert any("note" in p for p in cpp)


# ─── Full run() integration ───────────────────────────────────────────────────


def test_no_dependency_files(tmp_path):
    result = run({"path": str(tmp_path)})
    assert result["result"] is None
    assert "No dependency files found" in result["error"]


def test_detects_outdated_python(tmp_path):
    write(tmp_path, "requirements.txt", "requests==2.28.0\n")
    with (
        patch.object(h, "get_pypi_latest", return_value="2.31.0"),
        patch.object(h, "get_osv_vulnerabilities", side_effect=no_vulns),
    ):
        result = run({"path": str(tmp_path)})
    pkg = result["result"]["findings"]["python"][0]
    assert pkg["outdated"] is True and pkg["latest_version"] == "2.31.0"


def test_detects_vulnerable_go(tmp_path):
    write(tmp_path, "go.mod", "module x\n\nrequire github.com/gin-gonic/gin v1.9.0\n")
    with (
        patch.object(h, "get_go_latest", return_value="v1.9.1"),
        patch.object(h, "get_osv_vulnerabilities", side_effect=mock_vuln),
    ):
        result = run({"path": str(tmp_path)})
    go_pkgs = result["result"]["findings"]["go"]
    assert go_pkgs[0]["vulnerable"] is True


def test_detects_outdated_java_maven(tmp_path):
    content = """\
<project>
  <dependencies>
    <dependency>
      <groupId>org.springframework</groupId>
      <artifactId>spring-core</artifactId>
      <version>5.3.29</version>
    </dependency>
  </dependencies>
</project>
"""
    write(tmp_path, "pom.xml", content)
    with (
        patch.object(h, "get_maven_latest", return_value="6.1.0"),
        patch.object(h, "get_osv_vulnerabilities", side_effect=no_vulns),
    ):
        result = run({"path": str(tmp_path)})
    java_pkgs = result["result"]["findings"]["java"]
    assert java_pkgs[0]["outdated"] is True


def test_multi_ecosystem_project(tmp_path):
    write(tmp_path, "requirements.txt", "requests==2.31.0\n")
    write(tmp_path, "package.json", json.dumps({"dependencies": {"axios": "1.4.0"}}))
    write(tmp_path, "go.mod", "module x\n\nrequire github.com/gin-gonic/gin v1.9.1\n")
    with (
        patch.object(h, "get_pypi_latest", return_value="2.31.0"),
        patch.object(h, "get_npm_latest", return_value="1.4.0"),
        patch.object(h, "get_go_latest", return_value="v1.9.1"),
        patch.object(h, "get_osv_vulnerabilities", side_effect=no_vulns),
    ):
        result = run({"path": str(tmp_path)})
    findings = result["result"]["findings"]
    assert "python" in findings
    assert "javascript" in findings
    assert "go" in findings
    assert result["result"]["summary"]["total"] == 3


def test_deduplicates_across_files(tmp_path):
    write(tmp_path, "requirements.txt", "requests==2.28.0\n")
    write(tmp_path, "pyproject.toml", '[project]\ndependencies = ["requests==2.28.0"]\n')
    with (
        patch.object(h, "get_pypi_latest", return_value="2.28.0"),
        patch.object(h, "get_osv_vulnerabilities", side_effect=no_vulns),
    ):
        result = run({"path": str(tmp_path)})
    python = result["result"]["findings"]["python"]
    assert sum(1 for p in python if p["package"] == "requests") == 1


def test_vulnerable_sorted_first(tmp_path):
    write(tmp_path, "requirements.txt", "httpx==0.24.0\nrequests==2.28.0\n")

    def mock_latest(name):
        return {"httpx": "0.24.0", "requests": "2.28.0"}.get(name)

    def selective_vuln(name, version, eco):
        return mock_vuln(name, version, eco) if name == "requests" else []

    with (
        patch.object(h, "get_pypi_latest", side_effect=mock_latest),
        patch.object(h, "get_osv_vulnerabilities", side_effect=selective_vuln),
    ):
        result = run({"path": str(tmp_path)})
    python = result["result"]["findings"]["python"]
    assert python[0]["package"] == "requests"


def test_malformed_pom_xml_reported_as_parse_error(tmp_path):
    write(tmp_path, "pom.xml", "NOT XML ][")
    result = run({"path": str(tmp_path)})
    assert result["error"] is None
    assert any("pom.xml" in e for e in result["result"].get("parse_errors", []))


def test_invalid_path():
    result = run({"path": "/nonexistent/path/abc123"})
    assert result["result"] is None
    assert result["error"] is not None


def test_summary_totals_correct(tmp_path):
    write(tmp_path, "requirements.txt", "requests==2.28.0\nflask==2.0.0\nhttpx==0.24.0\n")

    def mock_latest(name):
        return {"requests": "2.31.0", "flask": "2.0.0", "httpx": "0.24.0"}.get(name)

    def selective_vuln(name, version, eco):
        return mock_vuln(name, version, eco) if name == "flask" else []

    with (
        patch.object(h, "get_pypi_latest", side_effect=mock_latest),
        patch.object(h, "get_osv_vulnerabilities", side_effect=selective_vuln),
    ):
        result = run({"path": str(tmp_path)})
    s = result["result"]["summary"]
    assert s["total"] == 3
    assert s["outdated"] == 1
    assert s["vulnerable"] == 1
    assert s["up_to_date"] == 1
    assert s["total"] == s["outdated"] + s["vulnerable"] + s["up_to_date"]
