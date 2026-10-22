resource "aws_opensearchserverless_security_policy" "encryption" {
  name = "${var.project_name}-encryption"
  type = "encryption"

  policy = jsonencode({
    Rules = [
      {
        Resource     = ["collection/${var.project_name}-vector"]
        ResourceType = "collection"
      }
    ]
    AWSOwnedKey = true
  })
}

resource "aws_opensearchserverless_security_policy" "network" {
  name = "${var.project_name}-network"
  type = "network"

  policy = jsonencode([
    {
      Description = "Public access for AIOps vector collection"
      Rules = [
        {
          ResourceType = "collection"
          Resource     = ["collection/${var.project_name}-vector"]
        },
        {
          ResourceType = "dashboard"
          Resource     = ["collection/${var.project_name}-vector"]
        }
      ]
      AllowFromPublic = true
    }
  ])
}

resource "aws_opensearchserverless_collection" "vector" {
  name = "${var.project_name}-vector"
  type = "VECTORSEARCH"

  depends_on = [
    aws_opensearchserverless_security_policy.encryption,
    aws_opensearchserverless_security_policy.network
  ]

  tags = var.tags
}

resource "aws_opensearchserverless_access_policy" "aiops" {
  name        = "${var.project_name}-data-access"
  type        = "data"
  description = "Data access for root console plus AIOps Lambda roles"

  policy = jsonencode([
    {
      Rules = [
        {
          ResourceType = "collection"
          Resource = [
            "collection/${var.project_name}-vector"
          ]
          Permission = [
            "aoss:DescribeCollectionItems",
            "aoss:CreateCollectionItems",
            "aoss:UpdateCollectionItems"
          ]
        },
        {
          ResourceType = "index"
          Resource = [
            "index/${var.project_name}-vector/*"
          ]
          Permission = [
            "aoss:CreateIndex",
            "aoss:DescribeIndex",
            "aoss:UpdateIndex",
            "aoss:DeleteIndex",
            "aoss:ReadDocument",
            "aoss:WriteDocument"
          ]
        }
      ]
      Principal = [
        "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root",
        aws_iam_role.aiops_ingest.arn,
        aws_iam_role.aiops_runbook_ingester.arn,
        aws_iam_role.aiops_remediation.arn
      ]
    }
  ])

  depends_on = [aws_opensearchserverless_collection.vector]
}
