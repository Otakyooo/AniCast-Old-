import type { Metadata } from "next";
import { PageShell } from "../../components/page-shell";
import { getI18n } from "../../i18n/server";
import styles from "./page.module.css";

export const metadata: Metadata = { title: "Anicast Backups — Privacy" };

export default async function BackupPrivacyPage() {
  const { locale } = await getI18n();
  const english = locale === "en";
  const sections = english ? [
    ["Purpose", "Anicast Backups is a private administration tool used by the Anicast operator to back up and restore the service. Visitors do not need to connect a Google account."],
    ["Google Drive access", "The operator authorizes rclone to read, create and remove backup files in the designated Google Drive folder. The Drive permission also allows access to other Drive files; the backup configuration restricts operations to the backup folder. Backups are encrypted before upload."],
    ["Storage and use", "OAuth credentials are stored in private operator configuration and encrypted recovery archives. They are used for backup and recovery, not advertising. The backup tool does not sell Google user data or use it to train AI models. Google Drive stores the encrypted archives under the operator’s account."],
    ["Retention and revocation", "The scheduled offsite retention is 90 days. The operator can revoke the application's access in Google Account settings and remove backup files from Drive. Revocation stops future access but does not itself delete existing backups."],
    ["Contact", "For questions about Anicast Backups, contact support@anicast.online. Updated 9 September 2026."],
  ] : [
    ["Назначение", "Anicast Backups — закрытый инструмент администратора Anicast для резервного копирования и восстановления сервиса. Посетителям сайта не нужно подключать Google-аккаунт."],
    ["Доступ к Google Drive", "Администратор разрешает rclone читать, создавать и удалять резервные копии в выделенной папке Google Drive. Разрешение Drive технически даёт доступ и к другим файлам; конфигурация резервного копирования ограничивает операции папкой бэкапов. Архивы шифруются перед загрузкой."],
    ["Хранение и использование", "Учётные данные OAuth хранятся в приватной конфигурации администратора и зашифрованных комплектах восстановления. Они используются для резервного копирования и восстановления, а не рекламы. Инструмент не продаёт данные Google и не использует их для обучения моделей ИИ. Google Drive хранит зашифрованные архивы в аккаунте администратора."],
    ["Срок хранения и отзыв доступа", "Плановый срок хранения внешних копий — 90 дней. Администратор может отозвать доступ приложения в настройках Google-аккаунта и удалить копии из Drive. Отзыв прекращает дальнейший доступ, но сам по себе не удаляет существующие архивы."],
    ["Контакт", "По вопросам Anicast Backups: support@anicast.online. Обновлено 9 сентября 2026 года."],
  ];
  return <PageShell active="home" back={{ href: "/", label: english ? "Home" : "Главная" }} heading={{ title: english ? "Anicast Backups privacy" : "Конфиденциальность Anicast Backups" }}>
    <article className={styles.article}>{sections.map(([title, text]) => <section key={title}><h2>{title}</h2><p>{text}</p></section>)}</article>
  </PageShell>;
}
