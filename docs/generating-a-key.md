# Generating your signing key

Registering binds one public key to your entrant. You keep the private half and
sign every forecast with it; we never see it and cannot recover it.

What the form wants is the **raw 32-byte Ed25519 public key, base64-encoded**:
44 characters from `A-Z a-z 0-9 + /`, ending in `=`.

```
+f/MmhW389yF/NJVycQM0knDfv1cSzyFX/9YJg/9rN8=
```

## With the arena's tool

```sh
python tools/submit_signed_forecast.py --generate-key entrant.key
```

It writes the private key to `entrant.key` with mode 600 and prints the public
key. Paste what it prints.

## With openssl, if you would rather not clone anything

```sh
openssl genpkey -algorithm ed25519 -out entrant.pem
openssl pkey -in entrant.pem -outform DER  | tail -c 32 > entrant.key
openssl pkey -in entrant.pem -pubout -outform DER | tail -c 32 | base64
chmod 600 entrant.pem entrant.key
```

The last command prints the 44 characters to paste. `tail -c 32` is doing the
real work in both: it drops the DER header and keeps only the key itself.

The middle line matters. `openssl` writes PEM, and the arena's client wants the
private key as the raw 32 bytes, so `entrant.key` -- not `entrant.pem` -- is what
you pass to `--key`. Handing it the PEM fails with *An Ed25519 private key is 32
bytes long*.

## Three things that are not this key

Each of these looks plausible and will leave the **Submit registration** button
grey, because the form checks the shape before it lets you through.

**A fingerprint.** Hex, usually 40 or 64 characters, no `=`:

```
bc041e513fc3e99eff8e6237ed5e429d49a85a8c        ← 40 hex characters, not a key
```

**An SSH key.** GitHub's own "Generating a new SSH key" page gives you this, and
it is the easiest mistake to make because it is also base64:

```
AAAAC3NzaC1lZDI1NTE5AAAAIDsIGwPltuAH6k4c3D/zOIe0so4K0Rps7kVRawlvdGqd
```

That is SSH wire format: a type tag, a length, and then the key. 68 characters,
no `=`. **`ssh-keygen` is the wrong tool here** -- use one of the two commands
above instead.

**The private key.** It never leaves your machine. If you paste something that
starts with `-----BEGIN PRIVATE KEY-----`, generate a fresh pair and treat the
old one as compromised.

## If you already have an SSH Ed25519 key

A dedicated key is better -- one key, one job, and revoking it later costs you
nothing else. If you want to reuse the one you have, the 32 bytes are inside it:

```sh
cut -d' ' -f2 ~/.ssh/id_ed25519.pub | base64 -d | tail -c 32 | base64
```

Signing then needs the matching private key in raw form, which `ssh-keygen` does
not export directly. This is more work than generating a new pair.

## Looking after the private key

- It stays on the machine that submits. Never commit it, never paste it into a
  page, an issue or a chat.
- Losing it means opening a pull request to register a new key: add a new entry
  with a new `id`, and set `"revoked": true` on the old one. Ownership stays with
  your GitHub account, so nobody else can do this for you.
- Answers you already filed stay verifiable: each one records the registration
  commit it was checked against, so rotating a key does not invalidate history.
