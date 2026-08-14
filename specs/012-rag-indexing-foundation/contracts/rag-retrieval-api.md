# Protected RAG Retrieval HTTP Contract

The HTTP route is a bounded verification boundary over the reusable retrieval
service. It is not a chatbot route and does not generate an LLM answer.

## Request

Method and path:

    GET /api/v1/rag/retrieval?query=<bounded-text>&limit=<optional-int>

Authentication:

- Requires the existing bearer-token authentication dependency.
- The server loads the current database User and active session.
- The route does not trust a JWT role claim and does not accept authorization
  scope from the client.

Parameters:

| Parameter | Rules |
|---|---|
| query | Required non-blank text; bounded to the configured query length. |
| limit | Optional positive integer; capped by the configured retrieval maximum. |

The request must not contain or honor User ID, Player ID, role, Team ID,
age-group, authorized-user list, or scope-expansion fields. A query embedding
may be accepted by the internal service contract, but this HTTP route accepts
text only so provider selection remains server-side.

## Successful response

Status: 200

    {
      "results": [
        {
          "chunk_id": "uuid",
          "document_id": "uuid",
          "source_type": "player_profile",
          "source_key": "stable-source-key",
          "text": "safe canonical chunk text",
          "score": 0.1234,
          "provenance": {
            "source_type": "player_profile",
            "source_entity_id": "uuid"
          }
        }
      ],
      "returned_count": 1,
      "limit": 5
    }

Results are already authorization-filtered by the database candidate query.
The response contains no vector, provider request, credential, User-ID ACL,
unapproved source field, or raw provider error. An authenticated unlinked
Player receives a valid empty result list for Player/team-specific retrieval.

## Error behavior

- 401: existing unauthenticated response.
- 422: invalid, blank, oversized, or out-of-range query/limit.
- 503: sanitized provider/index compatibility failure; never include provider
  credentials, request bodies, vectors, or raw exception text.
- 500: existing sanitized server error handling for unexpected failures.

Retrieval does not create Business Audit or authentication audit events. It is a
read boundary and does not expose an unrestricted vector-search variant.

## Authorization requirements

The service must apply the current role, active User state, linked Player state,
TeamCoach assignments, TeamPlayer memberships, active Player state, Team IDs,
and age groups inside the query that orders by vector similarity. Application
code must not receive a broad candidate set and remove forbidden rows afterward.
