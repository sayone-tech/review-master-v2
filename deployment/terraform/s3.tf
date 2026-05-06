#checkov:skip=CKV_AWS_144:Cross-region replication not needed at this scale
#checkov:skip=CKV_AWS_18:S3 access logging not needed at this scale
#checkov:skip=CKV_AWS_21:Static files don't need versioning
#checkov:skip=CKV_AWS_145:AES256 default encryption is sufficient for public static assets
#checkov:skip=CKV2_AWS_61:No lifecycle rules needed for static assets
#checkov:skip=CKV2_AWS_62:S3 event notifications not required
resource "aws_s3_bucket" "static" {
  bucket = "review-master-static-${var.environment}"
  tags   = { Name = "review-master-static-${var.environment}" }
}

#checkov:skip=CKV2_AWS_6:Public access is intentional — bucket serves public static files via bucket policy
resource "aws_s3_bucket_public_access_block" "static" {
  bucket = aws_s3_bucket.static.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "static" {
  bucket     = aws_s3_bucket.static.id
  depends_on = [aws_s3_bucket_public_access_block.static]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicReadStaticFiles"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.static.arn}/static/*"
    }]
  })
}

resource "aws_s3_bucket_cors_configuration" "static" {
  bucket = aws_s3_bucket.static.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET"]
    allowed_origins = ["https://${var.domain_name}", "https://www.${var.domain_name}"]
    max_age_seconds = 3600
  }
}
