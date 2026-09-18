from datetime import date
from decimal import Decimal

from app.models.allocation_map import ApiKeyDepartmentMap, ManualAllocation, TagDepartmentMap
from app.models.cost_line_item import AllocationMethod
from app.models.department import Department
from app.models.usage_record import UsageRecord, UsageSourceType
from app.services.allocation_service import resolve_allocations


def make_usage(provider_id, sku="sku", quantity=100, period_start=date(2026, 1, 15), **kwargs):
    return UsageRecord(
        provider_id=provider_id,
        sku_code=sku,
        quantity=Decimal(quantity),
        unit="tokens",
        period_start=period_start,
        period_end=period_start,
        source_type=UsageSourceType.csv_import,
        source_reference="test",
        **kwargs,
    )


def test_direct_department_wins_even_if_mappings_exist(db_session, anthropic_provider, engineering_dept):
    marketing = Department(name="Marketing", code="MKT")
    db_session.add(marketing)
    db_session.commit()

    db_session.add(
        ApiKeyDepartmentMap(
            provider_id=anthropic_provider.id,
            api_key_label="key-xyz",
            department_id=marketing.id,
            effective_from=date(2026, 1, 1),
        )
    )
    db_session.commit()

    usage = make_usage(
        anthropic_provider.id, department_id=engineering_dept.id, api_key_label="key-xyz"
    )
    db_session.add(usage)
    db_session.commit()
    db_session.refresh(usage)

    allocations = resolve_allocations(db_session, usage)

    assert len(allocations) == 1
    assert allocations[0].department_id == engineering_dept.id
    assert allocations[0].method == AllocationMethod.direct


def test_key_mapping_used_when_no_direct_department(db_session, anthropic_provider, engineering_dept):
    key_map = ApiKeyDepartmentMap(
        provider_id=anthropic_provider.id,
        api_key_label="key-eng",
        department_id=engineering_dept.id,
        effective_from=date(2026, 1, 1),
    )
    db_session.add(key_map)
    db_session.commit()

    usage = make_usage(anthropic_provider.id, api_key_label="key-eng")
    db_session.add(usage)
    db_session.commit()
    db_session.refresh(usage)

    allocations = resolve_allocations(db_session, usage)

    assert len(allocations) == 1
    assert allocations[0].department_id == engineering_dept.id
    assert allocations[0].method == AllocationMethod.key_mapping
    assert allocations[0].reference_id == key_map.id


def test_key_mapping_respects_effective_date_range(db_session, anthropic_provider, engineering_dept):
    db_session.add(
        ApiKeyDepartmentMap(
            provider_id=anthropic_provider.id,
            api_key_label="key-eng",
            department_id=engineering_dept.id,
            effective_from=date(2026, 3, 1),  # not yet active in January
        )
    )
    db_session.commit()

    usage = make_usage(anthropic_provider.id, api_key_label="key-eng", period_start=date(2026, 1, 15))
    db_session.add(usage)
    db_session.commit()
    db_session.refresh(usage)

    assert resolve_allocations(db_session, usage) == []


def test_tag_mapping_used_when_no_key_mapping(db_session, anthropic_provider, engineering_dept):
    tag_map = TagDepartmentMap(
        provider_id=anthropic_provider.id,
        tag_value="proj-alpha",
        department_id=engineering_dept.id,
        effective_from=date(2026, 1, 1),
    )
    db_session.add(tag_map)
    db_session.commit()

    usage = make_usage(anthropic_provider.id, tag_value="proj-alpha")
    db_session.add(usage)
    db_session.commit()
    db_session.refresh(usage)

    allocations = resolve_allocations(db_session, usage)

    assert len(allocations) == 1
    assert allocations[0].department_id == engineering_dept.id
    assert allocations[0].method == AllocationMethod.tag_mapping


def test_manual_split_across_departments_sums_to_total_fraction(db_session, anthropic_provider, engineering_dept):
    marketing = Department(name="Marketing", code="MKT")
    db_session.add(marketing)
    db_session.commit()

    usage = make_usage(anthropic_provider.id)
    db_session.add(usage)
    db_session.commit()
    db_session.refresh(usage)

    db_session.add_all(
        [
            ManualAllocation(
                usage_record_id=usage.id, department_id=engineering_dept.id, allocation_percent=Decimal("70")
            ),
            ManualAllocation(
                usage_record_id=usage.id, department_id=marketing.id, allocation_percent=Decimal("30")
            ),
        ]
    )
    db_session.commit()

    allocations = resolve_allocations(db_session, usage)

    assert len(allocations) == 2
    fractions = {a.department_id: a.fraction for a in allocations}
    assert fractions[engineering_dept.id] == Decimal("0.7")
    assert fractions[marketing.id] == Decimal("0.3")
    assert sum(fractions.values()) == Decimal("1.0")
    assert all(a.method == AllocationMethod.manual_split for a in allocations)


def test_no_mapping_at_all_returns_empty_never_defaults(db_session, anthropic_provider):
    usage = make_usage(anthropic_provider.id)
    db_session.add(usage)
    db_session.commit()
    db_session.refresh(usage)

    assert resolve_allocations(db_session, usage) == []
