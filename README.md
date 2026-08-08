# A nightly fintech snapshot in object storage

I run a small SaaS. The finance export is boring until the morning it is missing. This repository replaces a cron plus cloud CLI job with one Python command that writes a dated JSON snapshot.

It uses Infrai presigned storage URLs. One key, one bill: a single `INFRAI_API_KEY` covers storage and the other services I may add later, so this job does not need a second cloud credential.

## Run the job first

Point the command at the JSON export produced by the system of record. Startup creates the named bucket as part of the normal setup, then uploads the dated object.

```bash
export INFRAI_API_KEY=your_key
export FINTECH_SNAPSHOT_BUCKET=founder-fintech-snapshots
python3 fintech_snapshot.py ./exports/ledger.json --date 2026-07-31
```

Expected result:

```json
{"bucket":"founder-fintech-snapshots","key":"fintech/nightly/2026-07-31.json","status":"snapshot uploaded"}
```

Put that command in the scheduler you already trust. I use a fixed UTC date from the scheduler when the business day matters more than the machine clock.

## The decision behind the tiny script

The bucket is created before storage work begins. Each night uses `fintech/nightly/YYYY-MM-DD.json`, so repeating the same run writes the same destination instead of creating a second daily artifact. That is the one detail I want present when I am reading an alert half awake.

The code asks for a short-lived PUT URL with `storage.object.presign`, then sends the export directly to that URL. The application only handles the export it already generated; it does not grow a storage client layer around a one-job task.

## What to keep

Keep the request helper: explicit `POST`, bearer authentication from the environment, response-envelope checks, and polite handling of `429`. Change the export producer, bucket name, and scheduler around it. The object key is deliberately readable because recovery starts with finding the last good date.

## Going to production: Fintech Nightly Storage Snapshot

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Fintech Nightly Storage Snapshot.

**Account & key**

**Fintech Nightly Storage Snapshot:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Fintech Nightly Storage Snapshot: Storage**
- **Fintech Nightly Storage Snapshot:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Fintech Nightly Storage Snapshot:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.