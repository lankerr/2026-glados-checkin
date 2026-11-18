// Independent compatibility boundary. Never trade safety requirements for a browser fallback.
export function selectExtensionAPI(scope = globalThis) {
  const api = scope.browser ?? scope.chrome;
  if (!api?.runtime?.id) throw new Error('extension_runtime_unavailable');
  return api;
}
export async function restrictPersistentStorage(api) {
  if (typeof api?.storage?.local?.setAccessLevel !== 'function') {
    throw new Error('restricted_persistent_storage_unsupported');
  }
  // Do not catch and silently continue: an unavailable protection disables initialization.
  await api.storage.local.setAccessLevel({accessLevel: 'TRUSTED_CONTEXTS'});
}
