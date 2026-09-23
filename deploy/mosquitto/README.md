# Local Mosquitto fallback

These files are non-secret templates. Render `FARM_ID` and `DEVICE_ID` into a
root-owned ACL and create the password file interactively:

```bash
sudo mosquitto_passwd -c /etc/mosquitto/agrimind.passwd agrimind-device-DEVICE_ID
sudo mosquitto -c /etc/mosquitto/conf.d/agrimind.conf -t
```

`allow_anonymous false` and the per-device ACL are mandatory. The example binds
to loopback and intentionally omits TLS. For a listener reachable over a LAN,
use an isolated trusted network or configure a CA, server certificate and key;
TLS is required on shared or untrusted networks. Never commit rendered ACLs,
password files, private keys, or runtime persistence.
