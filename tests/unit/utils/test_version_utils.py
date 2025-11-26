from review_bot_automator.utils.version_utils import validate_version_constraint


def test_requirements_line_with_exact_pin_is_valid() -> None:
    result = validate_version_constraint("package==1.2.3", require_exact_pin=True)
    assert result.is_valid is True


def test_identity_operator_accepts_arbitrary_identifier() -> None:
    result = validate_version_constraint("package===foobar", require_exact_pin=True)
    assert result.is_valid is True


def test_equality_allows_trailing_wildcard_final_segment() -> None:
    assert validate_version_constraint("pkg==1.2.*", require_exact_pin=True).is_valid is True
    assert validate_version_constraint("pkg!=1.2.*", require_exact_pin=False).is_valid is True


def test_equality_rejects_middle_wildcard_segment() -> None:
    result = validate_version_constraint("pkg==1.*.2", require_exact_pin=True)
    assert result.is_valid is False
