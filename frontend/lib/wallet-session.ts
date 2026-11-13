export type WalletNetwork = "mainnet" | "testnet";
type ConnectedSession = {isSignedIn:()=>boolean;wallet:()=>Promise<{signOut:()=>Promise<void>}>};

// A single selector owns the session. Concurrent callers must not initialize
// separate instances or accidentally reuse a session for another network.
export function createWalletSession<T extends ConnectedSession>(
  load: (network: WalletNetwork) => Promise<T>,
  show: (selector: T) => Promise<void>,
) {
  let network: WalletNetwork | undefined;
  let pending: Promise<T> | undefined;

  async function get(target: WalletNetwork) {
    if (network && network !== target) throw new Error("Wallet network changed. Reload the page before reconnecting.");
    if (!pending) {
      network = target;
      pending = load(target).catch(error => {
        pending = undefined;
        network = undefined;
        throw error;
      });
    }
    return pending;
  }

  return {
    get,
    async connect(target: WalletNetwork, chooseWallet = false) {
      const selector = await get(target);
      if (chooseWallet || !selector.isSignedIn()) await show(selector);
      return selector;
    },
    async disconnect(target: WalletNetwork) {
      const selector = await get(target);
      if (selector.isSignedIn()) await (await selector.wallet()).signOut();
    },
  };
}
