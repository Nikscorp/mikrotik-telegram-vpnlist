# mikrotik-telegram-vpnlist [![Build Status](https://travis-ci.com/Nikscorp/mikrotik-telegram-vpnlist.svg?token=6pBsGa8d3N2ze5g6qb5U&branch=master)](https://travis-ci.com/Nikscorp/mikrotik-telegram-vpnlist)


Small telegram bot for resolving ips from given hosts and adding them to Mikrotik ip-list for static routing to vpn tunnel. 


## Usage

### Creating l2tp tunnel and address list

1. Create l2tp client connection
```
/interface l2tp-client
add connect-to=8.8.8.8 disabled=no ipsec-secret=bla \
    keepalive-timeout=disabled name=l2tp-out1-do password=\
    bla use-ipsec=yes user=bla
```
2. Add addresses to address-list

```
/ip firewall address-list
add address=1.1.1.1 comment=api.telegram.org list=test
```

3. Add mangle rules

```
/ip firewall mangle
add action=mark-routing chain=prerouting comment="mark test" \
    dst-address-list=test new-routing-mark="mark test" passthrough=\
    no src-address=192.168.88.0/24
```

4. Add nat rule

```
/ip firewall nat
add action=masquerade chain=srcnat out-interface=l2tp-out1-do
```

5. Add route rule

```
/ip route
add check-gateway=ping comment="to vpn" distance=1 gateway=\
    l2tp-out1-do routing-mark="mark test"
```

### Configure and use bot

#### Environment variables

- `TOKEN` -- Telegram bot token
- `MIKROTIK_USER` -- Mikrotik ssh user
- `MIKROTIK_ADDR` -- Mikrotik local addr
- `MIKROTIK_PORT` -- Mikrotik port
- `IP_LIST_NAME` -- Name of address-list to add - ips
- `LIST_OF_USERS` -- Coma-separated list of telegram user-ids allowed to execute commands

#### Bot commands

- `/unblock domain1 [ url2...]` -- Add ip of domain or url to ip-list for static routing to vpn tunnel
- `/help` -- Get help

