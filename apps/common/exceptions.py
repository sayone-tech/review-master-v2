from rest_framework.exceptions import APIException


class BusinessRuleViolation(APIException):
    status_code = 400
    default_detail = "Business rule violation."
    default_code = "business_rule_violation"
