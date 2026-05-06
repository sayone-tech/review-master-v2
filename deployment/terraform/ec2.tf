resource "aws_key_pair" "operator" {
  key_name   = "review-master-operator"
  public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIW/0mYPrfhjhpDQNJUt2NqWu4hi3MXUfSpf7zcy7anj renjithraj2005@gmail.com"
}

# Look up the latest Amazon Linux 2023 ARM64 AMI automatically
data "aws_ami" "al2023_arm64" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-arm64"]
  }

  filter {
    name   = "architecture"
    values = ["arm64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.al2023_arm64.id
  instance_type          = "t4g.medium"
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.ec2.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = aws_key_pair.operator.key_name

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 30
    delete_on_termination = true
    encrypted             = true
  }

  user_data = file("${path.module}/../scripts/user-data.sh")

  tags = { Name = "review-master-prod" }

  lifecycle {
    # Prevent Terraform from replacing the instance if AMI or user_data changes.
    # All app updates go through SSM Run Command (deploy.sh), not instance replacement.
    ignore_changes = [ami, user_data]
  }
}

resource "aws_eip_association" "app" {
  instance_id   = aws_instance.app.id
  allocation_id = aws_eip.ec2.allocation_id
}
