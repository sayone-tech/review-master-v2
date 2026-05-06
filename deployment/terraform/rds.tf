resource "random_password" "db_password" {
  length  = 32
  special = false # avoid shell-escaping issues in DATABASE_URL
}

resource "aws_ssm_parameter" "db_password" {
  name  = "/review-master/prod/DB_PASSWORD_RAW"
  type  = "SecureString"
  value = random_password.db_password.result

  lifecycle {
    ignore_changes = [value] # don't overwrite if manually rotated later
  }
}

resource "aws_db_instance" "main" {
  #checkov:skip=CKV_AWS_157:Single-AZ intentional — Multi-AZ added when second paying customer joins (+$13/mo)
  #checkov:skip=CKV_AWS_161:IAM auth not needed; password auth via DATABASE_URL is sufficient at this scale
  #checkov:skip=CKV_AWS_118:Enhanced monitoring adds cost; basic CloudWatch metrics sufficient for 60 users
  #checkov:skip=CKV_AWS_354:Performance Insights default encryption sufficient; CMK overkill at this scale
  #checkov:skip=CKV_AWS_129:Query logging via Parameter Group when needed; off by default to avoid log ingestion cost
  identifier            = "review-master-prod"
  engine                = "postgres"
  engine_version        = "16"
  instance_class        = "db.t4g.micro"
  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = "reviewmaster"
  username = var.db_username
  password = random_password.db_password.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  auto_minor_version_upgrade = true
  backup_retention_period    = 7
  backup_window              = "03:00-04:00" # UTC (08:30 IST)
  maintenance_window         = "Mon:04:00-Mon:05:00"

  skip_final_snapshot       = false
  final_snapshot_identifier = "review-master-prod-final"
  deletion_protection       = true

  performance_insights_enabled = true

  tags = { Name = "review-master-prod" }
}
