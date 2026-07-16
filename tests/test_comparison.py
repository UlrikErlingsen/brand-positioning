import pandas as pd
import pytest

from positionsignal.comparison import ComparisonConfig, analyze_position_comparisons


def comparison_data() -> pd.DataFrame:
    rows = []
    means = {
        "Alpha": (6.0, 5.0),
        "Beta": (4.0, 5.1),
        "Gamma": (3.0, 4.9),
    }
    for wave, wave_shift in (("W1", 0.0), ("W2", 0.4)):
        for segment, segment_shift in (("Core", 0.0), ("Growth", 0.2)):
            for brand, (innovative, trusted) in means.items():
                for respondent in range(8):
                    rows.append(
                        {
                            "respondent_id": f"{wave}-{segment}-{respondent}",
                            "wave": wave,
                            "segment": segment,
                            "brand": brand,
                            "innovative": innovative + (wave_shift if brand == "Alpha" else 0) + segment_shift,
                            "trusted": trusted + segment_shift,
                            "weight": 1.0,
                        }
                    )
    return pd.DataFrame(rows)


def test_wave_segment_ownership_and_pop_pod_are_reported() -> None:
    result = analyze_position_comparisons(
        comparison_data(),
        ComparisonConfig(
            brand_column="brand",
            attributes=("innovative", "trusted"),
            focus_brand="Alpha",
            wave_column="wave",
            reference_wave="W1",
            comparison_wave="W2",
            segment_column="segment",
            reference_segment="Core",
            comparison_segment="Growth",
            respondent_column="respondent_id",
            weight_column="weight",
            difference_threshold=0.3,
            parity_tolerance=0.15,
        ),
    )

    innovative = result.association_ownership.set_index("attribute").loc["innovative"]
    assert innovative["leader_brand"] == "Alpha"
    assert innovative["focus_lead_status"] == "DESCRIPTIVE LEADER"
    classifications = result.pop_pod.set_index("attribute")["classification"]
    assert classifications["innovative"] == "POINT OF DIFFERENCE CANDIDATE"
    assert classifications["trusted"] == "POINT OF PARITY CANDIDATE"
    assert not result.wave_change.empty
    assert not result.segment_change.empty
    assert result.current_profiles.loc["Alpha", "innovative"] == pytest.approx(6.6)


def test_ownership_only_mode_works_without_wave_or_segment() -> None:
    result = analyze_position_comparisons(
        comparison_data().query("wave == 'W2' and segment == 'Core'"),
        ComparisonConfig(
            brand_column="brand",
            attributes=("innovative", "trusted"),
            focus_brand="Alpha",
        ),
    )

    assert len(result.association_ownership) == 2
    assert result.wave_change.empty
    assert result.segment_change.empty
