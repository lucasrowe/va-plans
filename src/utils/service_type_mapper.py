"""Service type mapping utilities for flexible benefit matching."""

import logging
from typing import Dict, List, Optional

# Set up logger
logger = logging.getLogger(__name__)

# Therapy benefit mapping
# Maps user_needs service types to possible plan benefit labels
THERAPY_BENEFIT_MAPPING = {
    'speech_therapy_visits': [
        'speech_therapy',
        'speech_language_therapy',
        'therapy_services',
        'rehabilitation_services',
        'habilitation_services'
    ],
    'occupational_therapy_visits': [
        'occupational_therapy',
        'ot_therapy',
        'therapy_services',
        'rehabilitation_services',
        'habilitation_services'
    ]
}

# Additional service type mappings can be added here
SERVICE_TYPE_MAPPING = {
    'primary_care_visits': [
        'primary_care',
        'primary_care_visit',
        'pcp_visit',
        'office_visit_primary'
    ],
    'specialist_visits': [
        'specialist',
        'specialist_visit',
        'specialty_care',
        'office_visit_specialist'
    ],
    'er_visits': [
        'emergency_room',
        'er',
        'emergency_services',
        'emergency_care'
    ],
    'tier_1_generics_monthly': [
        'tier_1',
        'tier_1_generic',
        'generic_drug',
        'tier1_rx'
    ],
    'tier_4_specialty_monthly': [
        'tier_4',
        'tier_4_specialty',
        'specialty_drug',
        'tier4_rx'
    ],
    'inpatient_surgeries': [
        'inpatient_hospital',
        'hospital_stay',
        'inpatient_care',
        'hospitalization'
    ]
}

# Combine all mappings
ALL_SERVICE_MAPPINGS = {**SERVICE_TYPE_MAPPING, **THERAPY_BENEFIT_MAPPING}


def normalize_benefit_key(benefit_key: str) -> str:
    """
    Normalize a benefit key to lowercase with underscores.

    Args:
        benefit_key: Raw benefit key from plan data

    Returns:
        Normalized key string
    """
    # Convert to lowercase and replace spaces/hyphens with underscores
    normalized = benefit_key.lower().replace(' ', '_').replace('-', '_')
    # Remove any special characters except underscores
    normalized = ''.join(c for c in normalized if c.isalnum() or c == '_')
    return normalized


def find_matching_benefit(
    usage_type: str,
    plan_benefits: Dict[str, any],
    use_fallback: bool = True
) -> Optional[str]:
    """
    Find the best matching benefit rule in plan data for a given usage type.

    Args:
        usage_type: Service type from user_needs (e.g., 'speech_therapy_visits')
        plan_benefits: Dictionary of benefit rules from plan data
        use_fallback: Whether to use fallback mappings if exact match not found

    Returns:
        Matching benefit key from plan_benefits, or None if no match found
    """
    # Normalize all plan benefit keys
    normalized_benefits = {normalize_benefit_key(k): k for k in plan_benefits.keys()}

    # Try exact match first (normalize the usage_type)
    normalized_usage = normalize_benefit_key(usage_type)
    if normalized_usage in normalized_benefits:
        logger.debug(f"Exact match found for '{usage_type}': '{normalized_benefits[normalized_usage]}'")
        return normalized_benefits[normalized_usage]

    # If no exact match and fallback is enabled, try mapped alternatives
    if use_fallback and usage_type in ALL_SERVICE_MAPPINGS:
        for alternative in ALL_SERVICE_MAPPINGS[usage_type]:
            normalized_alt = normalize_benefit_key(alternative)
            if normalized_alt in normalized_benefits:
                logger.info(
                    f"Fallback mapping used for '{usage_type}': "
                    f"using '{normalized_benefits[normalized_alt]}' benefit"
                )
                return normalized_benefits[normalized_alt]

    # No match found
    logger.warning(f"No matching benefit found for '{usage_type}' in plan data")
    return None


def get_therapy_benefit_for_usage(
    usage_type: str,
    plan_benefits: Dict[str, any]
) -> Optional[str]:
    """
    Specialized function to find therapy benefits with intelligent fallback.

    This function implements the therapy mapping strategy:
    1. Try exact match (e.g., 'speech_therapy')
    2. Try specific therapy type (e.g., 'occupational_therapy')
    3. Fall back to combined 'therapy_services'
    4. Fall back to 'rehabilitation_services' or 'habilitation_services'

    Args:
        usage_type: Therapy usage type from user_needs
        plan_benefits: Dictionary of benefit rules from plan data

    Returns:
        Matching benefit key from plan_benefits, or None if no match found
    """
    if usage_type not in THERAPY_BENEFIT_MAPPING:
        logger.warning(f"'{usage_type}' is not a recognized therapy service type")
        return None

    # Try all mapped alternatives in order of preference
    normalized_benefits = {normalize_benefit_key(k): k for k in plan_benefits.keys()}

    for alternative in THERAPY_BENEFIT_MAPPING[usage_type]:
        normalized_alt = normalize_benefit_key(alternative)
        if normalized_alt in normalized_benefits:
            benefit_key = normalized_benefits[normalized_alt]
            if alternative in ['therapy_services', 'rehabilitation_services', 'habilitation_services']:
                logger.info(
                    f"Using combined therapy benefit for '{usage_type}': '{benefit_key}'"
                )
            else:
                logger.debug(
                    f"Found specific therapy benefit for '{usage_type}': '{benefit_key}'"
                )
            return benefit_key

    logger.warning(f"No therapy benefit found for '{usage_type}' in plan data")
    return None


def map_usage_to_standard_cost_key(usage_key: str) -> str:
    """
    Map a usage_profile key to its corresponding standard_costs key.

    Convention: usage keys end with count indicator (e.g., '_visits', '_monthly')
                cost keys end with '_cost' or '_visit'

    Examples:
        'primary_care_visits' -> 'primary_care_visit'
        'speech_therapy_visits' -> 'speech_therapy_visit'
        'tier_1_generics_monthly' -> 'tier_1_generic_cost'
        'tier_4_specialty_monthly' -> 'tier_4_specialty_cost'

    Args:
        usage_key: Key from usage_profile

    Returns:
        Corresponding key for standard_costs
    """
    # Handle monthly medications
    if usage_key.endswith('_monthly'):
        base = usage_key.replace('_monthly', '')
        # Handle tier naming variations
        if base.endswith('_generics'):
            base = base.replace('_generics', '_generic')
        if base.endswith('_specialty'):
            return f"{base}_cost"
        return f"{base}_cost"

    # Handle visit-based services
    if usage_key.endswith('_visits'):
        base = usage_key.replace('_visits', '')
        return f"{base}_visit"

    # Handle surgeries
    if usage_key.endswith('_surgeries'):
        base = usage_key.replace('_surgeries', '')
        return f"{base}_surgery"

    # Default: return as-is and let validation catch mismatches
    logger.warning(
        f"Unexpected usage_key format: '{usage_key}'. "
        f"Expected key ending in '_visits', '_monthly', or '_surgeries'"
    )
    return usage_key


def validate_usage_cost_pairing(
    usage_profile: Dict[str, any],
    standard_costs: Dict[str, any]
) -> List[str]:
    """
    Validate that all usage_profile items have corresponding standard_costs.

    Args:
        usage_profile: Usage configuration from user_needs
        standard_costs: Market rates from user_needs

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    for usage_key in usage_profile.keys():
        cost_key = map_usage_to_standard_cost_key(usage_key)

        if cost_key not in standard_costs:
            errors.append(
                f"Missing standard cost for '{usage_key}': "
                f"Expected '{cost_key}' in standard_costs"
            )

    return errors
