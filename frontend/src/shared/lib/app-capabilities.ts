/** Debe coincidir con lib/app_capabilities.py → CAPABILITIES_VERSION */
export const EXPECTED_CAPABILITIES_VERSION = 2;

export function isApiCapabilitiesStale(capabilitiesVersion: number | null | undefined): boolean {
  if (capabilitiesVersion == null || Number.isNaN(capabilitiesVersion)) {
    return true;
  }
  return capabilitiesVersion < EXPECTED_CAPABILITIES_VERSION;
}
