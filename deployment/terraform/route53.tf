#checkov:skip=CKV2_AWS_19:EIP is pre-created before EC2 launch; association happens via AWS console post-apply
resource "aws_eip" "ec2" {
  domain = "vpc"
  tags   = { Name = "review-master-ec2-eip" }
}

# Reference the existing hosted zone — Terraform will NEVER create or destroy it.
# DNS was already migrated from GoDaddy to Route 53 manually.
data "aws_route53_zone" "main" {
  name         = var.domain_name
  private_zone = false
}

resource "aws_route53_record" "apex" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = var.domain_name
  type    = "A"
  ttl     = 300
  records = [aws_eip.ec2.public_ip]
}

resource "aws_route53_record" "www" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "www.${var.domain_name}"
  type    = "A"
  ttl     = 300
  records = [aws_eip.ec2.public_ip]
}
