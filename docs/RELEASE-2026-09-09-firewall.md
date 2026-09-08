# Этап 3: firewall VPS, 09.09.2026

На production включена таблица `inet anicast_edge`. Публичные входящие порты:
TCP 22/80/443, UDP 443 (AWG). Relay и node-exporter доступны только MainServer
через awg0. Контроль Docker DNAT не позволяет будущей случайной публикации порта
обойти ограничения INPUT. Существующий выход MainServer через VPS сохранён.

## Подтверждённые проверки

- 24 изолированных сетевых сценария с настоящим nftables: IPv4/IPv6, host input,
  Docker DNAT, UDP, source restrictions, loopback, container/MainServer egress.
- nft --check, shell syntax, systemd-analyze verify; unit active и enabled.
- Новые отдельные SSH-подключения по публичному адресу и через 10.78.0.1 после
  включения правил. Host key публичного подключения проверен по известному ключу.
- Windows → public VPS: TCP 22/80/443 доступны, TCP 8443/9100/3000/9099 недоступны.
- MainServer → exporter: 200; relay с заведомо неверным тестовым токеном getMe: 401
  от Telegram (сообщения никому не отправлялись).
- VPS → backend readiness: 200; public home/API: 200.
- Prometheus `up{job="node-vps"}` = 1; verify-monitoring.sh прошёл.
- Повторный reload успешен; правила iptables/ip6tables совпадают с исходными
  без учёта счётчиков пакетов. AWG handshake обновляется, тестовые netns удалены.
- После внедрения на VPS доступно 501 MiB памяти; приложение healthy без рестарта.

## Развёртывание

Изменение без сборок образов, перезапуска приложения или новой фоновой службы.
Systemd oneshot загружает правила и завершается; правила исполняет ядро.
Параметры SSH и ключи не менялись. UFW остаётся masked/inactive — действующий
firewall проверять через Anicast unit и nft, а не ufw status.

Исходный ruleset и iptables/ip6tables snapshots сохранены на VPS в
`/root/anicast-firewall-20260909/`. Watchdog rollback.sh там же. Во время применения
был активен трёхминутный systemd timer отката; он отменён только после сетевых
проверок. Unit включён для следующей загрузки, но reboot в этой сессии не делался.

Решение и порядок отката: [ADR 003](architecture/003-vps-firewall.md).
Исходные удаления трёх пользовательских изображений не входят в этот коммит.

## Дальше

Сборки и релизы через CI/registry, репетиция восстановления на отдельном хосте.
Домашний MainServer и туннель остаются точками отказа; firewall этого не устраняет.
Внешний IPv6 на реальном VPS не проверен из-за отсутствия глобального IPv6;
IPv6-политика проверена в netns. Нагрузочный тест и внешний пентест не выполнялись.
