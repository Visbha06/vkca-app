# Player Account Linking API Contract

Base path: `/api/v1/players`. Every operation below requires an authenticated
Head Coach. Assistant Coaches and Players receive the existing `403 Not
authorized` response and receive no account-linking controls in the frontend.

Normal Player list/detail responses do not expose User account fields.

## Eligible account lookup

### `GET /api/v1/players/account-linking/users`

Query parameters:

| Name | Type | Default/constraint |
|---|---|---|
| `search` | string | optional trimmed search over safe name/email labels |
| `page` | integer | `1`, minimum `1` |
| `page_size` | integer | `20`, maximum `100` |

The result contains only unlinked Player-role accounts and safe fields:

```json
{
  "users": [
    {
      "id": "user-uuid",
      "display_name": "Rohan Patel",
      "email": "rohan@example.com",
      "role": "player",
      "is_active": true
    }
  ],
  "page": 1,
  "page_size": 20,
  "total_users": 1,
  "total_pages": 1
}
```

Passwords, hashes, sessions, tokens, and security-audit details are never
returned.

## Link

### `PUT /api/v1/players/{player_id}/account`

Request:

```json
{
  "user_id": "player-user-uuid",
  "version_number": 3
}
```

The Player version is the optimistic-concurrency token. The target must be a
valid unlinked Player-role User and the Player must be unlinked. Response `200`
returns the updated Player version and safe linked-account snapshot.

## Unlink

### `DELETE /api/v1/players/{player_id}/account`

Request body:

```json
{"version_number": 4}
```

The frontend requires explicit confirmation before sending the request. Both
records remain; only the association is cleared. Response `200` returns the
Player with `account: null`.

## Reassign

### `POST /api/v1/players/{player_id}/account/reassign`

Request:

```json
{
  "expected_user_id": "old-player-user-uuid",
  "new_user_id": "new-player-user-uuid",
  "version_number": 5
}
```

Reassignment is an explicit corrective mutation. The expected old account,
current Player version, and eligible new account must all match. It commits as
one association mutation and creates one `player.account_reassigned` event,
not separate unlink/link events.

## Success, errors, and audit

Successful link, unlink, and reassignment responses contain:

```json
{
  "player_id": "player-uuid",
  "account": {
    "id": "user-uuid",
    "display_name": "Rohan Patel",
    "email": "rohan@example.com",
    "role": "player",
    "is_active": true
  },
  "player_version_number": 6
}
```

Errors use the existing project conventions:

- `401` unauthenticated/expired session;
- `403` non-Head Coach access;
- `404` missing Player or User;
- `409` duplicate association, expected-account mismatch, or stale Player
  version;
- `422` malformed UUID, invalid role/operation, or missing confirmation.

The service uses the Business Audit registry. Reuse an existing action only if
its meaning is exact; otherwise register these explicit identifiers:

```text
player.account_linked
player.account_unlinked
player.account_reassigned
```

Each successful mutation stages exactly one event in the same transaction.
Rejected, unauthorized, stale, integrity-failed, and rolled-back requests
stage none.

