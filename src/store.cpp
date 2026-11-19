#include "store.h"

#include <Preferences.h>
#include <string.h>

namespace store {
namespace {

constexpr char kNamespace[] = "inkotp";
// Bump when a stored struct changes shape; older blobs are then ignored.
constexpr uint8_t kAccountVersion = 1;
constexpr uint8_t kSettingsVersion = 1;

struct AccountRecord {
    uint8_t version;
    otp::Account account;
};

struct SettingsRecord {
    uint8_t version;
    Settings settings;
};

Preferences prefs;
uint32_t usedMask = 0;
// Slots in display order. Kept as one small value so that reordering is a
// single write and can never lose an account.
uint8_t order[kMaxAccounts];
int numOrder = 0;
Settings current;
Net nets[kMaxNets];
int numNets = 0;

void slotKey(int slot, char* key) { snprintf(key, 8, "acct%d", slot); }

int orderIndex(int slot) {
    for (int i = 0; i < numOrder; i++) {
        if (order[i] == slot) return i;
    }
    return -1;
}

void saveOrder() {
    if (numOrder == 0) {
        prefs.remove("order");
    } else {
        prefs.putBytes("order", order, numOrder);
    }
}

void defaults(Settings& s) {
    memset(&s, 0, sizeof(s));
    s.sleepSecs = 60;
    s.unlockSecs = 0;
    s.maxTries = 10;
    s.autoSync = true;
}

void saveNets() {
    if (numNets == 0) {
        prefs.remove("nets");
    } else {
        prefs.putBytes("nets", nets, sizeof(Net) * numNets);
    }
}

}  // namespace

void begin() {
    prefs.begin(kNamespace, false);

    usedMask = 0;
    for (int slot = 0; slot < kMaxAccounts; slot++) {
        char key[8];
        slotKey(slot, key);
        if (prefs.getBytesLength(key) == sizeof(AccountRecord)) usedMask |= 1u << slot;
    }

    // Trust the stored order only as far as it matches the accounts that exist;
    // anything it misses goes at the end.
    uint8_t stored[kMaxAccounts];
    size_t stored_len = prefs.getBytesLength("order");
    if (stored_len > sizeof(stored)) stored_len = 0;
    if (stored_len > 0) prefs.getBytes("order", stored, stored_len);
    numOrder = 0;
    for (size_t i = 0; i < stored_len; i++) {
        if (used(stored[i]) && orderIndex(stored[i]) < 0) order[numOrder++] = stored[i];
    }
    for (int slot = 0; slot < kMaxAccounts; slot++) {
        if (used(slot) && orderIndex(slot) < 0) order[numOrder++] = (uint8_t)slot;
    }

    SettingsRecord rec;
    if (prefs.getBytes("settings", &rec, sizeof(rec)) == sizeof(rec) &&
        rec.version == kSettingsVersion) {
        current = rec.settings;
        current.owner[sizeof(current.owner) - 1] = '\0';
        current.flags &= kCompact | kSounds;
    } else {
        defaults(current);
    }

    size_t len = prefs.getBytesLength("nets");
    numNets = 0;
    if (len > 0 && len % sizeof(Net) == 0 && len <= sizeof(nets)) {
        prefs.getBytes("nets", nets, len);
        numNets = (int)(len / sizeof(Net));
        for (int i = 0; i < numNets; i++) {
            nets[i].ssid[sizeof(nets[i].ssid) - 1] = '\0';
            nets[i].pass[sizeof(nets[i].pass) - 1] = '\0';
        }
    }
}

bool used(int slot) { return slot >= 0 && slot < kMaxAccounts && (usedMask >> slot & 1); }

int count() { return numOrder; }

int slotAt(int n) { return n >= 0 && n < numOrder ? order[n] : -1; }

bool move(int slot, int delta) {
    const int from = orderIndex(slot);
    const int to = from + delta;
    if (from < 0 || to < 0 || to >= numOrder || (delta != 1 && delta != -1)) return false;
    order[from] = order[to];
    order[to] = (uint8_t)slot;
    saveOrder();
    return true;
}

bool load(int slot, otp::Account& out) {
    if (!used(slot)) return false;
    char key[8];
    slotKey(slot, key);
    AccountRecord rec;
    bool ok = prefs.getBytes(key, &rec, sizeof(rec)) == sizeof(rec) &&
              rec.version == kAccountVersion && rec.account.secretLen <= otp::kMaxSecret &&
              otp::validParams(rec.account.algo, rec.account.digits, rec.account.period);
    if (ok) {
        out = rec.account;
        out.label[otp::kMaxLabel] = '\0';
    }
    memset(&rec, 0, sizeof(rec));
    return ok;
}

bool save(int slot, const otp::Account& account) {
    if (slot < 0 || slot >= kMaxAccounts) return false;
    char key[8];
    slotKey(slot, key);
    AccountRecord rec;
    memset(&rec, 0, sizeof(rec));
    rec.version = kAccountVersion;
    rec.account = account;
    bool ok = prefs.putBytes(key, &rec, sizeof(rec)) == sizeof(rec);
    memset(&rec, 0, sizeof(rec));
    if (ok && !used(slot)) {
        usedMask |= 1u << slot;
        order[numOrder++] = (uint8_t)slot;
        saveOrder();
    }
    return ok;
}

int add(const otp::Account& account) {
    for (int slot = 0; slot < kMaxAccounts; slot++) {
        if (!used(slot)) return save(slot, account) ? slot : -1;
    }
    return -1;
}

void remove(int slot) {
    if (!used(slot)) return;
    char key[8];
    slotKey(slot, key);
    prefs.remove(key);
    const int at = orderIndex(slot);
    memmove(&order[at], &order[at + 1], numOrder - at - 1);
    numOrder--;
    usedMask &= ~(1u << slot);
    saveOrder();
}

Settings& settings() { return current; }

void saveSettings() {
    SettingsRecord rec;
    memset(&rec, 0, sizeof(rec));
    rec.version = kSettingsVersion;
    rec.settings = current;
    prefs.putBytes("settings", &rec, sizeof(rec));
}

int netCount() { return numNets; }

bool net(int index, Net& out) {
    if (index < 0 || index >= numNets) return false;
    out = nets[index];
    return true;
}

bool saveNet(const char* ssid, const char* pass) {
    if (!ssid[0] || strlen(ssid) >= sizeof(Net::ssid) || strlen(pass) >= sizeof(Net::pass)) {
        return false;
    }
    int i = 0;
    while (i < numNets && strcmp(nets[i].ssid, ssid) != 0) i++;
    if (i == kMaxNets) return false;
    memset(&nets[i], 0, sizeof(Net));
    strcpy(nets[i].ssid, ssid);
    strcpy(nets[i].pass, pass);
    if (i == numNets) numNets++;
    saveNets();
    return true;
}

void removeNet(const char* ssid) {
    for (int i = 0; i < numNets; i++) {
        if (strcmp(nets[i].ssid, ssid) != 0) continue;
        memmove(&nets[i], &nets[i + 1], sizeof(Net) * (numNets - i - 1));
        numNets--;
        memset(&nets[numNets], 0, sizeof(Net));
        saveNets();
        return;
    }
}

void wipeAll() {
    prefs.clear();
    usedMask = 0;
    numOrder = 0;
    numNets = 0;
    memset(nets, 0, sizeof(nets));
    defaults(current);
}

}  // namespace store
