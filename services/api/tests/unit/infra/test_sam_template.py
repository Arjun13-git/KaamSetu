"""Guardrails on the deployment template: it must stay consistent with the code that the rest of the
suite proves, and it must not quietly grow more privilege."""

import importlib.util
import re
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from app.core.config import MIN_DEMO_KEY_LENGTH
from app.providers.persistence.dynamodb.table import table_definition

REPO_ROOT = Path(__file__).resolve().parents[5]
AWS_DIR = REPO_ROOT / "infrastructure" / "aws"
BUILD_SCRIPT = REPO_ROOT / "services" / "api" / "scripts" / "build_lambda.py"


class _CloudFormationLoader(yaml.SafeLoader):
    """Reads CloudFormation short-form tags (``!Ref``, ``!Sub`` ...) as plain mappings."""


def _tag(loader: yaml.SafeLoader, suffix: str, node: yaml.Node) -> dict[str, Any]:
    if isinstance(node, yaml.ScalarNode):
        value: Any = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)  # type: ignore[arg-type]
    return {"Ref" if suffix == "Ref" else f"Fn::{suffix}": value}


_CloudFormationLoader.add_multi_constructor("!", _tag)


@pytest.fixture(scope="module")
def template() -> dict[str, Any]:
    loaded = yaml.load((AWS_DIR / "template.yaml").read_text(), Loader=_CloudFormationLoader)
    assert isinstance(loaded, dict)
    return loaded


@pytest.fixture(scope="module")
def build_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_lambda", BUILD_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _function(template: dict[str, Any]) -> dict[str, Any]:
    props: dict[str, Any] = template["Resources"]["ApiFunction"]["Properties"]
    return props


def test_the_table_matches_the_definition_the_adapter_is_tested_against(
    template: dict[str, Any],
) -> None:
    expected = table_definition("unused")
    actual = template["Resources"]["DataTable"]["Properties"]

    assert actual["BillingMode"] == expected["BillingMode"]
    assert actual["KeySchema"] == expected["KeySchema"]
    assert actual["AttributeDefinitions"] == expected["AttributeDefinitions"]
    assert actual["GlobalSecondaryIndexes"] == expected["GlobalSecondaryIndexes"]


def test_the_function_uses_the_lambda_entry_point_and_the_runtime_the_build_targets(
    template: dict[str, Any], build_script: ModuleType
) -> None:
    function = _function(template)

    assert function["Handler"] == "app.lambda_handler.handler"
    assert function["Runtime"] == f"python{build_script.LAMBDA_PYTHON}"
    assert function["Architectures"] == ["x86_64"]
    assert any("x86_64" in platform for platform in build_script.LAMBDA_PLATFORMS)
    assert not any("aarch64" in platform for platform in build_script.LAMBDA_PLATFORMS)


def test_the_function_runs_in_demo_mode_on_dynamodb(template: dict[str, Any]) -> None:
    variables = _function(template)["Environment"]["Variables"]

    assert variables["APP_ENV"] == "demo"
    assert variables["DATA_PROVIDER"] == "dynamodb"
    assert variables["DYNAMODB_TABLE"] == {"Ref": "DataTable"}
    assert variables["DEMO_API_KEY"] == {"Ref": "DemoApiKey"}
    assert "AWS_REGION" not in variables  # reserved: Lambda sets it


def test_the_demo_key_is_a_hidden_required_parameter_with_no_default(
    template: dict[str, Any],
) -> None:
    parameter = template["Parameters"]["DemoApiKey"]

    assert parameter["NoEcho"] is True
    assert parameter["MinLength"] >= MIN_DEMO_KEY_LENGTH
    assert "Default" not in parameter


def _statements(template: dict[str, Any]) -> dict[str, dict[str, Any]]:
    (policy,) = _function(template)["Policies"]
    return {statement["Sid"]: statement for statement in policy["Statement"]}


def test_the_function_has_exactly_two_grants_and_no_managed_policy_beyond_the_default(
    template: dict[str, Any],
) -> None:
    assert set(_statements(template)) == {"KaamSetuTableAccess", "InvokeTheConfiguredModelOnly"}
    assert "ManagedPolicyArns" not in _function(template)


def test_the_function_can_only_read_write_and_query_its_own_table(template: dict[str, Any]) -> None:
    statement = _statements(template)["KaamSetuTableAccess"]

    assert statement["Effect"] == "Allow"
    assert set(statement["Action"]) == {"dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query"}
    assert statement["Resource"] == [
        {"Fn::GetAtt": "DataTable.Arn"},
        {"Fn::Sub": "${DataTable.Arn}/index/*"},
    ]


def test_the_function_can_invoke_only_the_configured_bedrock_model(
    template: dict[str, Any],
) -> None:
    statement = _statements(template)["InvokeTheConfiguredModelOnly"]

    assert statement["Effect"] == "Allow"
    assert statement["Action"] == ["bedrock:InvokeModel"]  # nothing else: no listing, no agents
    one_model_in_this_region = (
        "arn:${AWS::Partition}:bedrock:${AWS::Region}::foundation-model/${BedrockModelId}"
    )
    assert statement["Resource"] == [{"Fn::Sub": one_model_in_this_region}]  # no wildcard
    assert "Condition" not in statement


def test_the_bedrock_model_is_one_parameter_with_no_wildcard(template: dict[str, Any]) -> None:
    parameters = template["Parameters"]

    assert parameters["BedrockModelId"]["Default"] == "amazon.nova-lite-v1:0"
    assert "*" not in parameters["BedrockModelId"]["Default"]
    assert "BedrockFoundationModelId" not in parameters  # no second model can be authorized


def test_the_deploy_script_passes_the_same_model_the_template_defaults_to(
    template: dict[str, Any],
) -> None:
    """SAM keeps an existing stack's old parameter values, so the script must state the model."""
    script = (AWS_DIR / "deploy.sh").read_text()
    match = re.search(r'model_id="\$\{KAAMSETU_BEDROCK_MODEL_ID:-([^}]+)\}"', script)

    assert match is not None
    assert match.group(1) == template["Parameters"]["BedrockModelId"]["Default"]
    assert '"BedrockModelId=$model_id"' in script


def test_the_function_is_configured_for_bedrock_from_parameters_not_literals(
    template: dict[str, Any],
) -> None:
    variables = _function(template)["Environment"]["Variables"]

    assert variables["LLM_PROVIDER"] == "bedrock"
    assert variables["LLM_MODEL"] == {"Ref": "BedrockModelId"}
    assert variables["DEFAULT_TIMEZONE"] == {"Ref": "DefaultTimezone"}


def test_the_timeout_fits_every_model_attempt_and_api_gateways_limit(
    template: dict[str, Any],
) -> None:
    function = _function(template)
    variables = function["Environment"]["Variables"]
    worst_case_model_time = float(variables["AI_TIMEOUT_SECONDS"]) * (
        1 + int(variables["AI_MAX_RETRIES"])
    )

    assert function["Timeout"] > worst_case_model_time  # leaves room for storage and start-up
    assert function["Timeout"] < 30  # API Gateway (HTTP API) integration limit


def test_no_resource_in_the_template_is_a_wildcard_grant(template: dict[str, Any]) -> None:
    serialized = yaml.safe_dump(template)

    assert "dynamodb:*" not in serialized
    assert "'*'" not in serialized and '"*"' not in serialized


def test_the_api_is_throttled_and_routes_everything_to_the_function(
    template: dict[str, Any],
) -> None:
    api = template["Resources"]["HttpApi"]["Properties"]["DefaultRouteSettings"]
    (event,) = _function(template)["Events"].values()

    assert api["ThrottlingBurstLimit"] > 0 and api["ThrottlingRateLimit"] > 0
    assert event["Type"] == "HttpApi"
    assert event["Properties"]["ApiId"] == {"Ref": "HttpApi"}
    assert event["Properties"]["Path"] == "/{proxy+}"


def test_logs_are_kept_in_a_group_with_finite_retention(template: dict[str, Any]) -> None:
    group = template["Resources"]["ApiLogGroup"]["Properties"]

    assert group["RetentionInDays"] == {"Ref": "LogRetentionDays"}
    assert _function(template)["LoggingConfig"]["LogGroup"] == {"Ref": "ApiLogGroup"}


def test_the_lambda_package_holds_the_runtime_dependencies_and_not_local_only_ones(
    build_script: ModuleType,
) -> None:
    names = {build_script._distribution_name(r) for r in build_script.lambda_requirements()}

    assert {"fastapi", "pydantic", "pydantic-settings", "mangum"} <= names
    assert names.isdisjoint({"uvicorn", "boto3"})


def test_the_template_and_scripts_contain_no_credentials() -> None:
    files = [AWS_DIR / name for name in ("template.yaml", "deploy.sh", "smoke_test.py")]
    for path in [*files, BUILD_SCRIPT]:
        text = path.read_text()
        assert "AKIA" not in text and "aws_secret_access_key" not in text.lower()
