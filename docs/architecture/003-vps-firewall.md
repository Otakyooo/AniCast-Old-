# ADR 003: входящий firewall VPS

Дата: 09.09.2026 (Europe/Moscow). Статус: реализовано.

## Основания

На VPS INPUT/FORWARD имели policy ACCEPT. UFW inactive и masked; native nftables
service disabled. Docker использует iptables-nft, отдельная native nftables table
`ip anicast_awg_nat` обеспечивает masquerade для 10.78.0.0/24 через eth0.
Туннель — awg0, peer MainServer 10.78.0.2/32, ListenPort UDP 443.

Caddy использует host network, frontend опубликован на loopback TCP 3000,
node-exporter — на tunnel IP TCP 9100. Обычный INPUT firewall не ограничивает
Docker DNAT в FORWARD. Простое включение UFW не закрывает эту границу.

## Решение

Собственная таблица `inet anicast_edge`, hook priority -10 перед фильтрами Docker.
INPUT default drop, разрешены loopback, established/related, ICMP/ICMPv6.

| Источник | Назначение | Разрешение |
| --- | --- | --- |
| eth0 (публичная сеть) | VPS | TCP 22/80/443, UDP 443 |
| awg0, 10.78.0.2 | VPS | TCP 22/8443/9100 |
| awg0, 10.78.0.2 | Docker node-exporter | Только DNAT исходного 10.78.0.1:9100 |
| awg0, 10.78.0.2 | eth0 | Сохранён существующий выход через VPS |
| eth0 / awg0, остальной новый forwarded traffic | Docker/прочие маршруты | Drop |
| Прочий forwarded traffic | Docker egress/bridges | Передаётся последующим правилам Docker |

SSH остаётся публичным: в текущем sshd password authentication запрещена,
root принимает только ключи. IP allowlist не вводится без стабильного адреса
оператора. IPv6 фильтруется той же таблицей; глобального IPv6 на VPS сейчас нет.
ICMPv6 разрешён для neighbour discovery и path MTU.

UFW/nftables.service не включаются, их настройки не переписываются. Systemd unit
`anicast-firewall.service` применяет правила до network-pre и Docker при загрузке.
Это oneshot, новый постоянный процесс/контейнер не требуется. Docker tables,
AWG NAT, маршруты и параметры SSH не изменяются. Глобальный flush ruleset запрещён.

## Применение и откат

`scripts/apply-vps-firewall.sh` собирает одну nft transaction: удалить только
старую Anicast table (если есть), затем создать новую. Сначала nft --check,
затем атомарная загрузка. Для эксплуатации установлены:

- `/etc/anicast/firewall.nft`;
- `/usr/local/sbin/anicast-firewall-apply`;
- `/etc/systemd/system/anicast-firewall.service`.

Перед изменениями сохранить ruleset, открыть независимый public SSH с проверкой
того же host key, поставить watchdog через systemd-run. В этом релизе watchdog
через 3 минуты отключал только Anicast unit/table. После новых public/tunnel SSH,
site/API/relay/metrics и внешних TCP probes таймер отменён. Не отменять watchdog
на основании одного уже установленного SSH-сеанса.

Для полной отмены первого внедрения: `systemctl disable --now anicast-firewall`.
Это открывает прежнюю границу INPUT, оставляя Docker/AWG rules; выполнять только
как осознанное восстановление доступа. Для обычного изменения конфигурации
сохранять предыдущий firewall.nft и откатывать его той же атомарной загрузкой.
Не восстанавливать старый полный ruleset поверх более новых Docker контейнеров.

## Проверки и ограничения

24 проверки настоящими пакетами в временных Linux netns: IPv4, IPv6, UDP туннеля,
loopback, Docker DNAT, блокирование чужого source, egress контейнера и MainServer.
Изолированная проверка повторной загрузки подтверждает replace transaction.
Production probes и сведения о резервной копии — в [отчёте](../RELEASE-2026-09-09-firewall.md).
Ребут VPS не выполнялся; boot order проверен systemd-analyze verify и enable.
Одна внешняя точка проверки не является полноценным внешним пентестом.

## Источники

- [Docker: packet filtering, ограничения UFW](https://docs.docker.com/engine/network/packet-filtering-firewalls/).
- [Docker: iptables и forwarding](https://docs.docker.com/engine/network/firewall-iptables/).
