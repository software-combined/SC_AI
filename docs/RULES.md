# Rules

These rules decide where new code goes and which way imports point.
Paths are relative to `router/`. See the [architecture map](ARCHITECTURE.md).

1. `provider_defs.py` owns every upstream fact (host, endpoint prefixes, key
   location, model catalogue, key-info endpoint, failure dialect) and imports
   nothing, so `packaging/` can spec-load it without the router package. `registry.py`
   imports only stdlib plus that leaf. Nothing in `ai_router/` may make the
   registry import a client, CLI, installer, or HTTP module. Client listing
   and config modules consume it; never the reverse.
2. HTTP transport owns loopback auth, body limits, drain/inflight, and
   connection cleanup: `ingress.py` owns auth/rebinding, body limits, GET
   routes and error shaping; `relay.py` owns the upstream relay loop; and
   `router.py` keeps drain/inflight plus POST orchestration over both.
   Windows connection cleanup uses `client_close.py` to half-close the response
   and discard at most 64 KiB of late request bytes within 250 ms, without
   parsing request framing. This preserves early refusals for split-write
   clients within that grace; POSIX keeps the standard-library close path.
   `transport.MAX_REQUEST_BYTES` (256 MiB) is the local hard ceiling on wire,
   decoded and prepared bytes for every route and encoding, checked by
   `ingress.read_body`, `router.Handler.admit` and again on every send in
   `transport.post_with_phases`; `Prepared.decoded_body_bytes` keeps a
   compressed passthrough from being under-counted. `runtime.MAX_BODY`
   (16 MiB) is only the threshold for shared large-request reservations.
   `request_lease.py` owns the 1 GiB budget, reservations, bounded waits and scalar
   diagnostics. Its condition uses the server lock; releases and draining wake
   waiters. A first reservation waits up to 60 seconds for space. Existing
   holders grow without waiting, preventing deadlock while they retain bodies;
   the budget is therefore an admission target, not a hard process-memory limit.
   One request above the budget can start when no reservation exists.
   After preparation returns, the controller releases a reservation when the
   request fits the threshold and retains neither fallback nor response adapter.
   Otherwise it spans relay and cleanup. Retry admission counts both retained
   bodies and reacquires a released reservation before any additional send.
   `turn_budget.BODY_BUDGET` shapes external Responses turns only; native
   bodies are forwarded whole. Protocol representation lives in `providers.py` (Responses/Messages) and
   `claude.py` (Messages ingress).
3. Upstream adapters own target/credential construction and are
   parameterized by one `ProviderDef`, never by a provider-name branch. A
   new external provider is a table entry plus registry rows; a provider
   with a different wire format is a new adapter class, never a branch in
   the request path.
   AWS Bedrock is the second external provider. Its Mantle endpoint reuses
   the native Responses and Messages wire formats, so it adds no adapter
   class: `provider_defs.BEDROCK` owns the regional host builder, the
   `/v1` and `/anthropic` prefixes and the Bedrock API key location. A
   registry row may narrow its provider's protocols with `protocols`;
   `registry.row_serves` is the one rule routing, pickers, candidate
   evidence and the route matrix read. Availability keeps one snapshot
   per external provider (its own key, region and file), and pickers read
   the combined set while routing gates each provider on its own
   snapshot. Bedrock has no summary rows, so its compaction fails closed. `image_provider.py` owns the native Images wire format;
   `protocols/images.py` selects the originating chat's connection;
   `media_origin.py` retains bounded, content-free turn bindings after chat
   preparation. Standalone calls without provenance keep their profile contract.
   `video_provider.py` owns Responses video job submission. Both use `media.py`
   for media envelopes and retain
   the shared credential, admission and transport boundaries. Media rows do
   not enter the chat projection. [Media generation](models/media-generation.md)
   records the client contract and preview limits. `media_cli.py` owns the
   explicit fallback command, including bounded video polling, a recovery
   receipt and exclusive output creation; it reuses the canonical adapters.
   `external_provider.py` owns the region, provider identity and model
   authorization shared by chat and video adapters. It imports neither
   adapter; distinct wire formats remain in their own modules.
   External headers start fresh every request;
   subscription headers never accompany an externally billed request.
   `decisions.py` is the one client for a provider's typed-decision endpoint
   (Jev today): it holds no policy and answers only what it can validate, so
   every consumer fails closed on its refusals and nothing runs it by default.
4. Installer orchestration (`packaging/install.py`, `bundle.py`,
   `service.py`, `updater.py`) calls one explicit platform backend;
   `bundle.py` owns the release lifecycle (verify, install, prune,
   rollback). Unsupported OS is an explicit refusal. Backends do not import
   runtime providers or client catalogue policy.
   Shared installer modules add no platform tests; the few existing checks
   remain in `install.py` and `service.py`. Repair decisions ask the selected
   backend, or `platforms.host()` for the running machine. Every backend answers
   the repair hooks that `platforms.NoRepair` declares (interrupted recovery,
   maintenance staging and finish, timeout proof, control readiness and repair).
   macOS and Linux inherit its no-op defaults. The Windows backend inherits
   `windows_installation.Repair`, whose hooks run the installation journal, and
   `windows_installation` uses only public backend methods such as `state` and
   `drain_router`.
   `platforms/windows_tasks.py` owns fixed task names, structured access,
   principal/action checks and definition snapshots. `windows.py` scopes names to
   the account and owns lifecycle
   order. Owned legacy definitions remain available through registration and
   expected-version health checks. An active legacy updater keeps its ownership
   record until a later healthy install can remove it after exit.
   An active owned task missing from its scoped view uses the service-wide view,
   filtering its exact path before inspecting instance IDs. Restoration validates
   the saved principal and action even when the definition must be recreated.
   Text and binary installation restores share the atomic writer's comparison guard.
5. A client is not a provider and an OS is neither. New clients reuse a
   proven wire protocol; a new protocol lands only after its contract is
   verified against the installed client version.
6. `packaging/` file-based imports avoid depending on a third-party
   distribution named `packaging`. Installer modules load siblings through
   `packaging/loader.py`, a leaf imported by name from `sys.path`. It executes
   each file once per process, keyed by resolved path, so callers share one
   copy of each module's classes, globals and test seams. The stable
   `*_launch.py` launchers and the checkout build tool `release.py` keep their
   own loaders. The installer and the runtime both require Python 3.14.
   Tests that load router files into the test process use `tests/loading.py`,
   which returns a new module on every call and clears the packaging cache
   first, so its siblings are new copies too; child-process probes and some
   plugin-script and tool tests keep their own loader.
7. `tools/` holds checkout-run helpers (local probes, scans, key ceremonies)
   that are invoked by the developer or by CI, not by an installed router;
   `ci_unittest.py` owns bounded CI workers and their result reports, keeping
   unittest discovery and fixtures separate from router runtime behavior.
   `plugin_verification.py` owns conservative suite selection for local and CI
   checks; unknown scope retains full discovery. Windows handoff waits for its
   child and propagates failure instead of relying on process replacement.
   `windows_standard.py` selects core/native standard-user CI suites and reuses
   the unittest result recorder, including module-preserving core partitions.
   Full discovery and selected occurrences stay separate in its reports.
   Its PowerShell launcher owns account isolation,
   exact report validation and cleanup; each matrix entry has its own runner.
   `ci_environment.py` records non-secret runner inputs for diagnostic comparisons;
   it does not certify test completion or release acceptance.
   `packaging/` holds the modules an installed host executes. A new
   host-run script belongs in `packaging/`, even if nothing in `ai_router/`
   imports it. `packaging/release.py` includes only its named installed operator
   helpers from `tools/`; checkout verification tools stay outside the bundle.
   `tools/disable.py` is the installed-host remover that `packaging/install.py` runs.
