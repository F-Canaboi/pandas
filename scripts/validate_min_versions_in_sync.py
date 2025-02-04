#!/usr/bin/env python3
"""
Check pandas required and optional dependencies are synced across:

ci/deps/actions-.*-minimum_versions.yaml
pandas/compat/_optional.py
setup.cfg

TODO: doc/source/getting_started/install.rst

This is meant to be run as a pre-commit hook - to run it manually, you can do:

    pre-commit run validate-min-versions-in-sync --all-files
"""
from __future__ import annotations

import configparser
import pathlib
import sys

DOC_PATH = pathlib.Path("doc/source/getting_started/install.rst").resolve()
CI_PATH = next(
    pathlib.Path("ci/deps").absolute().glob("actions-*-minimum_versions.yaml")
)
CODE_PATH = pathlib.Path("pandas/compat/_optional.py").resolve()
SETUP_PATH = pathlib.Path("setup.cfg").resolve()
EXCLUDE_DEPS = {"tzdata"}
# pandas package is not available
# in pre-commit environment
sys.path.append("pandas/compat")
sys.path.append("pandas/util")
import _exceptions
import version

sys.modules["pandas.util.version"] = version
sys.modules["pandas.util._exceptions"] = _exceptions
import _optional


def get_versions_from_code() -> dict[str, str]:
    install_map = _optional.INSTALL_MAPPING
    versions = _optional.VERSIONS
    for item in EXCLUDE_DEPS:
        versions.pop(item)
    return {
        install_map.get(k, k).casefold(): v
        for k, v in versions.items()
        if k != "pytest"
    }


def get_versions_from_ci(content: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    # Don't parse with pyyaml because it ignores comments we're looking for
    seen_required = False
    seen_optional = False
    required_deps = {}
    optional_deps = {}
    for line in content:
        if "# required dependencies" in line:
            seen_required = True
        elif "# optional dependencies" in line:
            seen_optional = True
        elif "- pip:" in line:
            continue
        elif seen_required and line.strip():
            if "==" in line:
                package, version = line.strip().split("==")

            else:
                package, version = line.strip().split("=")
            package = package[2:]
            if package in EXCLUDE_DEPS:
                continue
            if not seen_optional:
                required_deps[package.casefold()] = version
            else:
                optional_deps[package.casefold()] = version
    return required_deps, optional_deps


def get_versions_from_setup() -> dict[str, str]:
    install_map = _optional.INSTALL_MAPPING
    optional_dependencies = {}

    parser = configparser.ConfigParser()
    parser.read(SETUP_PATH)
    setup_optional = parser["options.extras_require"]["all"]
    dependencies = setup_optional[1:].split("\n")

    # remove test dependencies
    test = parser["options.extras_require"]["test"]
    test_dependencies = set(test[1:].split("\n"))
    dependencies = [
        package for package in dependencies if package not in test_dependencies
    ]

    for dependency in dependencies:
        package, version = dependency.strip().split(">=")
        optional_dependencies[install_map.get(package, package).casefold()] = version

    for item in EXCLUDE_DEPS:
        optional_dependencies.pop(item)

    return optional_dependencies


def main():
    with open(CI_PATH, encoding="utf-8") as f:
        _, ci_optional = get_versions_from_ci(f.readlines())
    code_optional = get_versions_from_code()
    setup_optional = get_versions_from_setup()

    diff = (ci_optional.items() | code_optional.items() | setup_optional.items()) - (
        ci_optional.items() & code_optional.items() & setup_optional.items()
    )

    if diff:
        packages = {package for package, _ in diff}
        out = sys.stdout
        out.write(
            f"The follow minimum version differences were found between  "
            f"{CI_PATH}, {CODE_PATH} AND {SETUP_PATH}. "
            f"Please ensure these are aligned: \n\n"
        )

        for package in packages:
            out.write(
                f"{package}\n"
                f"{CI_PATH}: {ci_optional.get(package, 'Not specified')}\n"
                f"{CODE_PATH}: {code_optional.get(package, 'Not specified')}\n"
                f"{SETUP_PATH}: {setup_optional.get(package, 'Not specified')}\n\n"
            )
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
