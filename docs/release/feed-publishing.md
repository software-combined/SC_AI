# Feed infrastructure and publishing

Two stacks, both in this repository, hold the update path. The `infra/`
templates are repository-only: deploy them from a checkout, not from an
installed host (the release bundle carries `README.md` and `docs/*.md` only).
Deploy the certificate first: CloudFront reads viewer certificates from `us-east-1`,
and the deploy stays in progress until ACM validates the DNS record it
creates in the `softwarecombined.com` zone.

```sh
aws cloudformation deploy --stack-name scg-router-feed-cert --region us-east-1 \
  --template-file infra/feed-cert.yaml --parameter-overrides HostedZoneId="$FEED_HOSTED_ZONE_ID"
CERT="$(aws cloudformation describe-stacks --stack-name scg-router-feed-cert \
  --region us-east-1 \
  --query "Stacks[0].Outputs[?OutputKey=='CertificateArn'].OutputValue" --output text)"
aws cloudformation deploy --stack-name scg-router-feed --region ap-southeast-2 \
  --template-file infra/feed.yaml --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides CertificateArn="$CERT" \
    BucketName="$FEED_BUCKET" SigningSeedArn="$FEED_SIGNING_SEED_ARN" \
    HostedZoneId="$FEED_HOSTED_ZONE_ID" ImmutableSubjectPrefix="$FEED_IMMUTABLE_SUBJECT"
```

Publication notices come from the central SCG AWS notification service. It
watches the same `bundles/` prefix with its own EventBridge rule and reports
each write as a branded publication, so the reader route needs no subscription
confirmation. That route belongs to the private infrastructure repository, so
its subscription list and source-stack alarms are the delivery checks.

The local formatter, topic, queue and narrow failure alarm stay as the rollback
path. They monitor only that local formatter rule, not central delivery.
`tests/test_feed_infra.py` compiles the inline function, drives it with a
hostile key and pins the grants.

To restore the direct route, deploy the version of `infra/feed.yaml` that
contains `FeedPublishSubscription`, passing `NotificationEmail="$EMAIL"` with
the deploy. The recipient must confirm the new SNS subscription, and the
rollback is incomplete until
`aws sns list-subscriptions-by-topic --topic-arn <topic>` no longer reports
`PendingConfirmation`. Do that same readback after an automatic stack rollback
that re-creates the subscription.

## Where the feed identifiers live (Plan 160)

The template carries no account-bearing default, and the tree carries no
account id, bucket name or role ARN. The release workflow reads three
**GitHub Actions secrets** (repository Actions settings, not the tree; never
written down here):

| Secret | What it is | What uses it |
|---|---|---|
| `FEED_BUCKET` | the feed bucket the publisher writes to | `tools/publish_feed.py --bucket`, the deploy override above |
| `FEED_ROLE` | the publisher role the release workflow assumes by OIDC | the workflow's AWS credentials step |
| `FEED_SIGNING_SEED_ARN` | the Secrets Manager secret holding the feed signing seed | the workflow's publish step, and the template's `SigningSeedArn` |

The repository owner sets and rotates these values through the trusted GitHub
Actions secret interface without printing them. GitHub masks their values in
workflow logs. The release preflight checks all three and fails closed before
checkout if any value is empty.

The feed serial must keep increasing across repositories, so a new repository's
workflow counter must not reset it. The repository variable
`RELEASE_SERIAL_OFFSET` holds the last live serial from the publication freeze
and stays fixed. The release builder adds the workflow run number to it, and
the release workflow refuses to publish from `software-combined/SC_AI` when the
variable is empty.

`FEED_STACK` stays a literal in the workflow: a stack name carries no account
id. Both publishers require `--bucket`, so a fork that runs them with no
arguments fails with a message naming the argument instead of publishing to
someone else's bucket.

`infra/feed.yaml` owns the versioned bucket (private to S3, served publicly
through CloudFront), the CloudFront distribution, the DNS alias, and the
publisher role. The role is assumable only by
`token.actions.githubusercontent.com`, and only for this repository's tag
refs: `repo:software-combined/SC_AI:ref:refs/tags/v*` in the
classic subject form, or
`repo:${ImmutableSubjectPrefix}:ref:refs/tags/v*`
in GitHub's immutable form. Supply the hosted-zone ID and immutable subject
from the private deployment configuration; the templates have no identifying
defaults. Existing stack updates retain their parameter values unless the
deployer explicitly overrides them. Publication retains this repository and
publisher identity; public forks receive no publishing grants or copied
GitHub Actions secrets. The role may read any object in the feed bucket and
write only release objects: `bundles/*`, `native-builds/*`, `installers/*`,
`install/*` and each channel's `latest.json`, `latest.json.sig` and `models.json`.
Native first-install publication remains acceptance-gated. The role can also list the
bucket, invalidate the feed, read the stack outputs and read the signing
seed. An explicit deny refuses a delete or any change to the bucket's own
configuration, so a later widening of the allow cannot reach them. The
first-install keys (`runtimes*`, `bootstrap/*`) are outside it on purpose:
that tool uploads with the operator's own credentials.

The publisher's bundle upload is create-only (`--if-none-match '*'`), so a
second write of a published key is refused by S3 itself. A role holder that
skips the flag can still replace a key: the central publication notification
reports it (one message per `bundles/*` write, so a second message for an
existing key is the signal), and bucket versioning recovers the replaced bytes
afterwards. When that second message arrives, recover deliberately: the
notification names the object and the version it wrote, so list that key's
versions (`aws s3api
list-object-versions --bucket "$FEED_BUCKET" --prefix bundles/<name>`),
match the notified `VersionId`, compare each version's `Metadata.sha256`
against the feed document that names the bundle, copy the matching version
back over the key with `aws s3api copy-object --copy-source
<bucket>/<key>?versionId=...`, then find out what held the publisher role.
The feed and its bundles are public: readers need no credential.

## When publication reporting fails

The central SCG AWS notification service owns replacement delivery and
reports both stages through its independent plain-text fallback.
`PublicationRuleFailures` alarms when EventBridge cannot send a bundle event
to the publication topic. `PublicationDeliveryFailures` alarms when that topic
cannot reach the shared notification intake. Both alarms sit in the
`AwsNotificationSources-*` source stack and must be checked before assuming a
publication was lost. The daily digest or notification state then confirms
whether the event was processed.

This stack's `FeedAlertFailureAlarm` is narrower: it covers only the retained
local formatter rule used by rollback. Its queue and function logs explain a
local invocation failure, but it does not establish that the central route
failed or that a reader missed a publication.

Verify the feed before trusting a release. Before the first publish the
channel documents do not exist; run the positive check after the first
release.

```sh
curl -s -o /dev/null -w '%{http_code}\n' https://dist.softwarecombined.com/stable/latest.json
# 200 once a release is published.
```

## Recover from a bad release

Feed bundles are immutable and the updater refuses a feed whose serial is
older than the last accepted one, so recovering from a bad release is
roll-forward: revert the change on the publishing branch, bump
`packaging/VERSION`, and tag again. Re-uploading a different bundle for an
already-published version aborts instead of replacing bytes, and a failed
workflow before the feed upload leaves the previous feed document serving.
A single host rolls back locally with `install.py --rollback --to <version>`
at an idle moment. Moving a host from `beta` back to `stable` needs
`<home>/feed-serial` cleared first, or the lower stable serial is refused
as stale.
