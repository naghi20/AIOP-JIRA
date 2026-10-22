# Create after terraform apply and collection Active

```json
PUT /aiops-runbooks
{
  "settings": { "index": { "knn": true } },
  "mappings": {
    "properties": {
      "content": { "type": "text" },
      "embedding": {
        "type": "knn_vector",
        "dimension": 1024,
        "method": { "name": "hnsw", "space_type": "cosinesimil" }
      },
      "title": { "type": "text" },
      "source": { "type": "keyword" },
      "doc_type": { "type": "keyword" },
      "created_at": { "type": "date" }
    }
  }
}
```
