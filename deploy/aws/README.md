# AWS Deployment (Fargate)

Minimal ECS/Fargate deployment scaffold.

## 1) Build and push image to ECR

```bash
aws ecr create-repository --repository-name reg-atlas

aws ecr get-login-password --region <region> | \
  docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com

docker build -t reg-atlas .
docker tag reg-atlas:latest <account>.dkr.ecr.<region>.amazonaws.com/reg-atlas:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/reg-atlas:latest
```

## 2) Update task definition

Edit:
- `deploy/aws/ecs/task-definition.json`
  - `image`: ECR image URL
  - `secrets`: Secrets Manager ARN for `OPENROUTER_API_KEY`

Register the task definition:
```bash
aws ecs register-task-definition --cli-input-json file://deploy/aws/ecs/task-definition.json
```

## 3) Create ECS cluster

```bash
aws ecs create-cluster --cli-input-json file://deploy/aws/ecs/cluster.json
```

## 4) Create ECS service

Edit:
- `deploy/aws/ecs/service.json`
  - `cluster`, `subnets`, `securityGroups`, `targetGroupArn`

Create service:
```bash
aws ecs create-service --cli-input-json file://deploy/aws/ecs/service.json
```

## 5) ALB Target Group (note)

Create a target group for port 8000 and use it in `service.json`. Attach the target group to an ALB listener.

## 6) Production add-ons

- Use RDS Postgres and S3 (Object Lock) for production storage
- Terminate TLS at ALB and restrict SG ingress
- Add CloudWatch alarms and logs

## Terraform (skeleton)

```bash
cd deploy/aws/terraform
terraform init
terraform plan
```
