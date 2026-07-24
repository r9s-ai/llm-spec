#!/usr/bin/env bash

set -euo pipefail

readonly MANAGED_LABEL="com.r9s.deploy.managed"
readonly MANAGED_VALUE="true"
readonly SERVICE_LABEL="com.r9s.deploy.service"
readonly SERVICE_VALUE="r9s-llm-spec"
readonly SLOT_LABEL="com.r9s.deploy.slot"

bundle_dir="${LLM_SPEC_BUNDLE_DIR:-$PWD}"
container_cli="${CONTAINER_CLI:-podman}"
container_name="${LLM_SPEC_CONTAINER_NAME:-r9s-llm-spec}"
image_repository="${LLM_SPEC_IMAGE_REPOSITORY:-r9s-llm-spec}"
blue_port="${LLM_SPEC_BLUE_PORT:-3092}"
green_port="${LLM_SPEC_GREEN_PORT:-3093}"
container_port="${LLM_SPEC_CONTAINER_PORT:-8788}"
revision="${GITHUB_SHA:-${LLM_SPEC_REVISION:-}}"
repository="${GITHUB_REPOSITORY:-r9s-ai/llm-spec}"
public_url="${LLM_SPEC_PUBLIC_URL:-https://llm-spec.inner.r9s.net}"
history_dir="${LLM_SPEC_HISTORY_DIR:-$HOME/r9s-llm-spec/history}"
health_timeout="${LLM_SPEC_HEALTH_TIMEOUT_SECONDS:-300}"
switch_timeout="${LLM_SPEC_SWITCH_TIMEOUT_SECONDS:-45}"
drain_seconds="${LLM_SPEC_NGINX_DRAIN_SECONDS:-10}"
nginx_site_source="$bundle_dir/nginx/llm-spec.inner.r9s.net.conf"
nginx_upstream_template="$bundle_dir/nginx/r9s-llm-spec-upstream.conf.template"
nginx_site_target="${LLM_SPEC_NGINX_SITE_CONFIG:-/etc/nginx/conf.d/r9s-llm-spec-site.conf}"
nginx_upstream_target="${LLM_SPEC_NGINX_UPSTREAM_CONFIG:-/etc/nginx/conf.d/r9s-llm-spec-upstream.conf}"

die() { echo "[llm-spec-deploy] error: $*" >&2; exit 1; }
log() { echo "[llm-spec-deploy] $*"; }

container_engine() {
  if [[ "$container_cli" == "podman" && "${1:-}" == "run" ]]; then
    env -u RUNNER_TRACKING_ID "$container_cli" "$@"
    return
  fi
  "$container_cli" "$@"
}

validate_port() {
  local name="$1" value="$2"
  if [[ ! "$value" =~ ^[0-9]+$ ]] || ((value < 1 || value > 65535)); then
    die "$name must be between 1 and 65535"
  fi
}

validate_inputs() {
  local target target_dir file
  [[ -d "$bundle_dir" ]] || die "bundle directory does not exist: $bundle_dir"
  [[ "$bundle_dir" = /* ]] || bundle_dir="$(cd "$bundle_dir" && pwd)"
  [[ "$container_cli" == "podman" || "$container_cli" == "docker" ]] \
    || die "CONTAINER_CLI must be podman or docker"
  command -v "$container_cli" >/dev/null 2>&1 || die "container CLI is unavailable"
  command -v curl >/dev/null 2>&1 || die "curl is required"
  command -v sudo >/dev/null 2>&1 || die "sudo is required"
  [[ "$container_name" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] || die "invalid container name"
  [[ "$image_repository" =~ ^[a-z0-9][a-z0-9._/-]*$ ]] || die "invalid image repository"
  validate_port LLM_SPEC_BLUE_PORT "$blue_port"
  validate_port LLM_SPEC_GREEN_PORT "$green_port"
  validate_port LLM_SPEC_CONTAINER_PORT "$container_port"
  [[ "$blue_port" != "$green_port" ]] || die "blue and green ports must differ"
  [[ "$revision" =~ ^[0-9a-f]{40}$ ]] || die "GITHUB_SHA must be a full commit SHA"
  [[ "$repository" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || die "invalid repository"
  [[ "$public_url" =~ ^https://[^[:space:]]+$ ]] || die "LLM_SPEC_PUBLIC_URL must be HTTPS"
  [[ "$history_dir" = /* ]] || die "LLM_SPEC_HISTORY_DIR must be absolute"
  if [[ ! "$health_timeout" =~ ^[0-9]+$ ]] || ((health_timeout < 10 || health_timeout > 1800)); then
    die "invalid health timeout"
  fi
  if [[ ! "$switch_timeout" =~ ^[0-9]+$ ]] || ((switch_timeout < 5 || switch_timeout > 300)); then
    die "invalid switch timeout"
  fi
  if [[ ! "$drain_seconds" =~ ^[0-9]+$ ]] || ((drain_seconds > 300)); then
    die "invalid drain seconds"
  fi
  for target in "$nginx_site_target" "$nginx_upstream_target"; do
    [[ "$target" = /* ]] || die "Nginx config paths must be absolute"
    target_dir="$(dirname "$target")"
    [[ -d "$target_dir" && -w "$target_dir" ]] || die "runner cannot update $target_dir"
  done
  for file in Dockerfile source.tar.gz revision.txt SHA256SUMS \
    nginx/llm-spec.inner.r9s.net.conf nginx/r9s-llm-spec-upstream.conf.template; do
    [[ -f "$bundle_dir/$file" ]] || die "missing deployment artifact: $file"
  done
}

verify_bundle() {
  local artifact_revision entry normalized listing
  (cd "$bundle_dir" && sha256sum --check --strict SHA256SUMS) \
    || die "deployment artifact checksum validation failed"
  artifact_revision="$(tr -d '[:space:]' < "$bundle_dir/revision.txt")"
  [[ "$artifact_revision" == "$revision" ]] || die "artifact revision does not match workflow revision"
  while IFS= read -r entry; do
    normalized="${entry#./}"
    [[ -z "$normalized" || "$normalized" == "." ]] && continue
    [[ "$entry" != /* && "$normalized" != ".." && "$normalized" != ../* \
      && "$normalized" != */.. && "$normalized" != */../* ]] \
      || die "unsafe path in source archive: $entry"
  done < <(tar -tzf "$bundle_dir/source.tar.gz")
  listing="$(tar -tvzf "$bundle_dir/source.tar.gz")"
  grep -Eq '^[lh]' <<<"$listing" && die "source archive must not contain links"
}

container_exists() { container_engine container inspect "$1" >/dev/null 2>&1; }
container_label() { container_engine container inspect --format "{{ index .Config.Labels \"$2\" }}" "$1" 2>/dev/null || true; }

assert_managed_container() {
  if [[ "$(container_label "$1" "$MANAGED_LABEL")" != "$MANAGED_VALUE" ]] \
    || [[ "$(container_label "$1" "$SERVICE_LABEL")" != "$SERVICE_VALUE" ]]; then
    die "container $1 is not managed by this deployment"
  fi
}

slot_for_port() {
  [[ "$1" == "$blue_port" ]] && { echo blue; return; }
  [[ "$1" == "$green_port" ]] && { echo green; return; }
  die "port $1 is not a registered slot"
}

container_for_port() { printf '%s-%s\n' "$container_name" "$(slot_for_port "$1")"; }

read_active_port() {
  local -a ports=()
  [[ -f "$nginx_upstream_target" ]] || { echo "$blue_port"; return; }
  mapfile -t ports < <(sed -nE 's/^[[:space:]]*server[[:space:]]+127\.0\.0\.1:([0-9]+);.*$/\1/p' "$nginx_upstream_target")
  ((${#ports[@]} == 1)) || die "managed Nginx upstream must contain one loopback server"
  [[ "${ports[0]}" == "$blue_port" || "${ports[0]}" == "$green_port" ]] \
    || die "Nginx upstream uses an unmanaged port"
  echo "${ports[0]}"
}

wait_for_healthy() {
  local name="$1" deadline status
  deadline=$((SECONDS + health_timeout))
  while ((SECONDS < deadline)); do
    status="$(container_engine inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$name" 2>/dev/null || true)"
    [[ "$status" == healthy ]] && return 0
    sleep 2
  done
  return 1
}

run_container() {
  local name="$1" image="$2" publish_port="$3" slot="$4" volume_spec
  local -a log_options health_options user_options
  volume_spec="$history_dir:/var/lib/llm-spec/history"
  log_options=()
  health_options=()
  user_options=()
  if [[ "$container_cli" == podman ]]; then
    log_options=(--log-driver k8s-file --log-opt max-size=20m)
    health_options=(--health-cmd "node -e \"fetch('http://127.0.0.1:' + (process.env.LLM_SPEC_BACKEND_PORT || '8788') + '/api/health').then((response) => { if (!response.ok) process.exit(1); }).catch(() => process.exit(1));\"" --health-interval 5s --health-timeout 5s --health-start-period 30s --health-retries 60)
    user_options=("--userns=keep-id:uid=1000,gid=1000")
    volume_spec+=":Z"
  else
    log_options=(--log-driver json-file --log-opt max-size=20m --log-opt max-file=3)
  fi
  container_engine run --detach --name "$name" --restart unless-stopped \
    --label "$MANAGED_LABEL=$MANAGED_VALUE" \
    --label "$SERVICE_LABEL=$SERVICE_VALUE" \
    --label "$SLOT_LABEL=$slot" \
    --label "org.opencontainers.image.revision=$revision" \
    --security-opt no-new-privileges:true --cap-drop ALL \
    "${log_options[@]}" "${health_options[@]}" "${user_options[@]}" \
    --env "LLM_SPEC_BACKEND_PORT=$container_port" \
    --env "LLM_SPEC_CORS_ORIGIN=$public_url" \
    --env "LLM_SPEC_HISTORY_DIR=/var/lib/llm-spec/history" \
    --env "LLM_SPEC_REVISION=$revision" \
    --volume "$volume_spec" \
    --publish "127.0.0.1:$publish_port:$container_port" "$image" >/dev/null
}

install_managed_file() {
  local source="$1" target="$2" temporary
  temporary="$(mktemp "$(dirname "$target")/.r9s-llm-spec.$(basename "$target").XXXXXX")"
  if ! cp "$source" "$temporary" || ! chmod 0644 "$temporary" || ! mv --force "$temporary" "$target"; then
    rm --force "$temporary"
    return 1
  fi
}

reload_nginx() { sudo -n /usr/sbin/nginx -t && sudo -n /usr/bin/systemctl reload nginx; }

verify_revision_url() {
  local url="$1" timeout="$2" deadline body
  deadline=$((SECONDS + timeout))
  while ((SECONDS < deadline)); do
    body="$(curl --fail --silent --show-error --max-time 15 "$url/api/health" 2>/dev/null || true)"
    grep -Fq "\"revision\":\"$revision\"" <<<"$body" && return 0
    sleep 1
  done
  return 1
}

restore_nginx_configs() {
  local site_backup="$1" upstream_backup="$2" site_existed="$3" upstream_existed="$4"
  if [[ "$site_existed" == 1 ]]; then
    install_managed_file "$site_backup" "$nginx_site_target"
  else
    rm --force "$nginx_site_target"
  fi
  if [[ "$upstream_existed" == 1 ]]; then
    install_managed_file "$upstream_backup" "$nginx_upstream_target"
  else
    rm --force "$nginx_upstream_target"
  fi
  reload_nginx || log "warning: failed to reload restored Nginx configuration"
}

switch_nginx() {
  local target_port="$1" work_dir="$2" rendered site_backup upstream_backup site_existed=0 upstream_existed=0
  rendered="$work_dir/r9s-llm-spec-upstream.conf"
  site_backup="$work_dir/nginx-site.backup"
  upstream_backup="$work_dir/nginx-upstream.backup"
  [[ -f "$nginx_site_target" ]] && { cp "$nginx_site_target" "$site_backup"; site_existed=1; }
  [[ -f "$nginx_upstream_target" ]] && { cp "$nginx_upstream_target" "$upstream_backup"; upstream_existed=1; }
  sed "s/__LLM_SPEC_UPSTREAM_PORT__/$target_port/g" "$nginx_upstream_template" > "$rendered"
  grep -Fq "server 127.0.0.1:$target_port;" "$rendered" || die "rendered upstream is invalid"
  grep -Fq '__LLM_SPEC_UPSTREAM_PORT__' "$rendered" && die "rendered upstream contains a placeholder"
  if ! install_managed_file "$nginx_site_source" "$nginx_site_target" \
    || ! install_managed_file "$rendered" "$nginx_upstream_target" \
    || ! reload_nginx; then
    restore_nginx_configs "$site_backup" "$upstream_backup" "$site_existed" "$upstream_existed"
    return 1
  fi
  if ! verify_revision_url "$public_url" "$switch_timeout"; then
    restore_nginx_configs "$site_backup" "$upstream_backup" "$site_existed" "$upstream_existed"
    return 1
  fi
}

cleanup_old_images() {
  local current previous image_id tag repository_name tag_name
  current="$(container_engine image inspect --format '{{.Id}}' "$image_repository:current" 2>/dev/null || true)"
  previous="$(container_engine image inspect --format '{{.Id}}' "$image_repository:previous" 2>/dev/null || true)"
  while IFS=$'\t' read -r image_id tag; do
    [[ -n "$image_id" && "$image_id" != "$current" && "$image_id" != "$previous" ]] || continue
    repository_name="${tag%:*}"; tag_name="${tag##*:}"
    [[ "$repository_name" == "$image_repository" && "$tag_name" != current && "$tag_name" != previous ]] || continue
    container_engine image rm "$tag" >/dev/null 2>&1 || true
  done < <(container_engine image ls --filter "label=$SERVICE_LABEL=$SERVICE_VALUE" --format '{{.ID}}\t{{.Repository}}:{{.Tag}}')
}

deploy() {
  local work_dir active_port target_port active_container target_container target_slot new_image previous_image="" source_url deployment_succeeded=0
  work_dir="$(mktemp -d "${RUNNER_TEMP:-/tmp}/r9s-llm-spec-deploy.XXXXXX")"
  new_image="$image_repository:$revision"
  source_url="https://github.com/$repository"
  mkdir -p "$history_dir"
  [[ -w "$history_dir" ]] || die "history directory is not writable"
  active_port="$(read_active_port)"
  [[ "$active_port" == "$blue_port" ]] && target_port="$green_port" || target_port="$blue_port"
  active_container="$(container_for_port "$active_port")"
  target_container="$(container_for_port "$target_port")"
  target_slot="$(slot_for_port "$target_port")"
  cleanup() {
    local routed_port
    routed_port="$(read_active_port 2>/dev/null || true)"
    if [[ "$deployment_succeeded" == 0 && "$routed_port" != "$target_port" ]] && container_exists "$target_container"; then
      if [[ "$(container_label "$target_container" "$MANAGED_LABEL")" == "$MANAGED_VALUE" ]]; then
        container_engine rm --force "$target_container" >/dev/null 2>&1 || true
      fi
    fi
    [[ "$deployment_succeeded" == 1 || "$routed_port" == "$target_port" ]] || container_engine image rm "$new_image" >/dev/null 2>&1 || true
    rm -rf -- "$work_dir"
  }
  trap cleanup EXIT
  if container_exists "$active_container"; then
    assert_managed_container "$active_container"
    previous_image="$(container_engine container inspect --format '{{.Image}}' "$active_container")"
  else
    previous_image="$(container_engine image inspect --format '{{.Id}}' "$image_repository:current" 2>/dev/null || true)"
  fi
  if container_exists "$target_container"; then
    assert_managed_container "$target_container"
    container_engine rm --force "$target_container" >/dev/null
  fi
  container_engine info >/dev/null 2>&1 || die "container runtime is unavailable"
  mkdir -p "$work_dir/source"
  tar -xzf "$bundle_dir/source.tar.gz" -C "$work_dir/source"
  cp "$bundle_dir/Dockerfile" "$work_dir/Dockerfile"
  log "building $new_image from validated artifact"
  container_engine build \
    --label "$MANAGED_LABEL=$MANAGED_VALUE" \
    --label "$SERVICE_LABEL=$SERVICE_VALUE" \
    --build-arg "SOURCE_REPOSITORY=$source_url" \
    --build-arg "SOURCE_REVISION=$revision" \
    --tag "$new_image" "$work_dir"
  log "starting $target_slot candidate on 127.0.0.1:$target_port"
  run_container "$target_container" "$new_image" "$target_port" "$target_slot"
  if ! wait_for_healthy "$target_container" || ! verify_revision_url "http://127.0.0.1:$target_port" 15; then
    container_engine logs --tail 120 "$target_container" 2>&1 || true
    die "candidate did not serve target revision; active service was not changed"
  fi
  switch_nginx "$target_port" "$work_dir" || die "Nginx cutover failed; active service was restored"
  deployment_succeeded=1
  [[ -z "$previous_image" ]] || container_engine image tag "$previous_image" "$image_repository:previous"
  container_engine image tag "$new_image" "$image_repository:current"
  if container_exists "$active_container"; then
    ((drain_seconds == 0)) || sleep "$drain_seconds"
    container_engine rm --force "$active_container" >/dev/null
  fi
  cleanup_old_images
  log "deployed revision $revision through Nginx on $target_slot"
  cleanup
  trap - EXIT
}

validate_inputs
verify_bundle
deploy
