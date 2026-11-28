import type { Metadata } from "next";
import Image from "next/image";
import { ArrowLeftRight, BarChart2, Plus, Receipt, Send, UserPlus, Wallet } from "@/components/icons";
import { ChatDemo, PaydayDemo, ReportDemo } from "./LandingDemos";
import { LandingMotion } from "./LandingMotion";
import styles from "./landing.module.css";

const telegram = "https://t.me/tillfold_bot";

export const metadata: Metadata = {
  title: "Tillfold — Catat pengeluaran, atur gaji, pantau arus kas",
  description: "Catat transaksi lewat Telegram, bagi gaji per siklus, dan pantau rekening, tagihan, serta target tabungan di dashboard Tillfold.",
  alternates: { canonical: "https://tillfold.alifihsan.my.id/" },
};

const chart = [33, 52, 27, 64, 39, 23, 48, 74, 29, 58, 42, 87, 45, 31];
const benefits = [
  { id: "contoh-chat", icon: Send, title: "Catat lewat Telegram", description: "Coba kirim transaksi dari chat." },
  { id: "contoh-gaji", icon: Wallet, title: "Atur anggaran per siklus", description: "Coba geser porsi uang harian." },
  { id: "contoh-arus-kas", icon: BarChart2, title: "Baca arus kas", description: "Pilih hari untuk lihat pengeluaran." },
];

const steps = [
  { icon: UserPlus, title: "Masuk atau buat akun", description: "Simpan catatan keuangan di akun Tillfold kamu." },
  { icon: Wallet, title: "Tambahkan rekening", description: "Masukkan rekening atau dompet yang kamu pakai dan saldo awalnya." },
  { icon: Receipt, title: "Catat transaksi pertama", description: "Catat dari dashboard atau hubungkan Telegram di pengaturan akun untuk mencatat lewat chat." },
  { icon: ArrowLeftRight, title: "Atur pembagian gaji", description: "Saat gajian, isi nominal tiap rekening tujuan dan cek batas belanja harianmu." },
];

const questions = [
  { question: "Harus pakai Telegram?", answer: "Bisa langsung catat dan kelola transaksi dari dashboard web. Telegram jadi pilihan kalau kamu lebih nyaman mencatat lewat chat." },
  { question: "Gimana cara mulai pakai bot?", answer: "Masuk ke dashboard, buka Pengaturan akun, lalu hubungkan Telegram. Setelah terhubung, coba ketik “kopi 25k mandiri” ke bot Tillfold." },
  { question: "Pembagian gaji harus sama tiap siklus?", answer: "Kamu masukin nominal sesuai kebutuhan tiap kali catat gaji. Tillfold menghitung persentasenya otomatis dari total gaji." },
  { question: "Apa transfer ikut dihitung sebagai pengeluaran?", answer: "Transfer antar rekening sendiri dicatat sebagai pindah saldo. Laporan arus kas memisahkannya dari pemasukan dan pengeluaran." },
];

function Brand() {
  return (
    <a className={styles.brand} href="/" aria-label="Tillfold">
      <Image src="/tillfold.svg" width={34} height={34} alt="" unoptimized />
      <span>Tillfold</span>
    </a>
  );
}

function CashFlowChart({ labels }: { labels?: boolean }) {
  return (
    <>
      <div className={styles.bars} aria-hidden="true">
        {chart.map((height, index) => (
          <span key={index} className={index === 11 ? styles.peak : undefined} style={{ height: `${height}%`, animationDelay: `${index * 28}ms` }} />
        ))}
      </div>
      {labels && <div className={styles.chartAxis} aria-hidden="true"><span>4 Mei</span><span>10 Mei</span><span>17 Mei</span></div>}
    </>
  );
}

function DashboardPreview() {
  return (
    <figure className={styles.preview} aria-labelledby="landing-preview-label">
      <figcaption id="landing-preview-label" className={styles.previewHeader}>
        <strong><Image src="/tillfold.svg" width={24} height={24} alt="" unoptimized /> Tillfold</strong>
        <span>Contoh dashboard</span>
      </figcaption>
      <div className={styles.previewBody}>
        <div className={styles.previewTitle}><strong>Ringkasan</strong><span>4–17 Mei</span></div>
        <div className={styles.previewMetrics}>
          <div className={styles.balance}><span>Total saldo</span><strong>Rp2.450.000</strong></div>
          <div className={styles.daily}><span>Batas harian</span><strong>Rp68.000</strong><span>8 hari tersisa</span></div>
        </div>
        <div className={styles.previewChart}>
          <div className={styles.previewTitle}><strong>Arus kas harian</strong><span>Pengeluaran</span></div>
          <CashFlowChart labels />
        </div>
      </div>
    </figure>
  );
}

export default function LandingPage() {
  return (
    <div id="tillfold-landing" className={styles.site}>
      <LandingMotion />
      <header className={`${styles.shell} ${styles.header}`} data-landing-header>
        <Brand />
        <nav aria-label="Navigasi landing page">
          <span className={styles.navIndicator} aria-hidden="true" />
          <a href="#fitur">Fitur</a>
          <a href="#cara-kerja">Cara kerja</a>
          <a href="#faq">FAQ</a>
        </nav>
        <a className={styles.headerAction} href="/dashboard">Masuk</a>
      </header>

      <main id="main-content" className={`${styles.shell} ${styles.sections}`}>
        <section className={`${styles.hero} ${styles.foldedCorner}`} aria-labelledby="landing-title" data-landing-hero>
          <div className={styles.heroBackdrop} aria-hidden="true">
            <Image src="/landing/steel-fold.webp" alt="" fill priority sizes="100vw" unoptimized />
          </div>
          <div className={styles.heroCopy}>
            <h1 id="landing-title"><span>Catat transaksi.</span>{" "}<span>Atur gaji.</span></h1>
            <p>Catat lewat Telegram, bagi gaji ke rekening tujuan, dan cek sisa uang belanja tiap hari.</p>
            <a className={styles.heroAction} href={telegram}>Coba bot Telegram</a>
          </div>
          <div className={styles.heroVisual}><DashboardPreview /></div>
        </section>

        <ul className={styles.benefits} aria-label="Keunggulan Tillfold">
          {benefits.map(({ id, icon: Icon, title, description }) => (
            <li key={id} data-landing-reveal>
              <a href={`#${id}`}>
                <span className={styles.benefitIcon}><Icon size={22} aria-hidden="true" /></span>
                <div><strong>{title}</strong><p>{description}</p></div>
              </a>
            </li>
          ))}
        </ul>

        <section id="fitur" className={`${styles.panel} ${styles.features}`} aria-labelledby="features-title">
          <div className={styles.featureHeading} data-landing-reveal>
            <h2 id="features-title">Dari catat sampai cek saldo.</h2>
            <p>Coba contoh interaktifnya di sini.</p>
          </div>
          <div className={styles.featureGrid}>
            <article id="contoh-chat" className={`${styles.feature} ${styles.foldedCorner}`} data-landing-reveal>
              <ChatDemo />
              <div className={styles.featureCopy}>
                <h3>Catat sebelum lupa</h3>
                <p>Kirim nominal dan nama rekening ke bot. Transaksinya muncul di dashboard.</p>
              </div>
            </article>

            <article id="contoh-gaji" className={`${styles.feature} ${styles.foldedCorner}`} data-landing-reveal>
              <PaydayDemo />
              <div className={styles.featureCopy}>
                <h3>Bagi gaji sesuai kebutuhan</h3>
                <p>Isi nominal tiap rekening tujuan. Tillfold langsung hitung persentasenya.</p>
              </div>
            </article>

            <article id="contoh-arus-kas" className={`${styles.feature} ${styles.foldedCorner}`} data-landing-reveal>
              <ReportDemo />
              <div className={styles.featureCopy}>
                <h3>Lihat pola belanja</h3>
                <p>Cek arus kas per hari, minggu, atau bulan dan buka transaksi yang membentuk angkanya.</p>
              </div>
            </article>
          </div>
        </section>

        <section id="cara-kerja" className={`${styles.panel} ${styles.guide}`} aria-labelledby="guide-title">
          <div className={`${styles.guideIntro} ${styles.foldedCorner}`} data-landing-reveal>
            <h2 id="guide-title">Cara mulai pakai Tillfold.</h2>
          </div>
          <ol>{steps.map(({ icon: Icon, title, description }, index) => (
            <li key={title} data-landing-reveal>
              <div className={styles.stepTop}><Icon size={22} aria-hidden="true" /><span aria-hidden="true">{index + 1}</span></div>
              <h3>{title}</h3>
              <p>{description}</p>
            </li>
          ))}</ol>
        </section>

        <section id="faq" className={`${styles.panel} ${styles.faq}`} aria-labelledby="faq-title">
          <h2 id="faq-title" data-landing-reveal>Yang sering ditanya</h2>
          <div>{questions.map(({ question, answer }) => (
            <details key={question} name="landing-faq" data-landing-reveal>
              <summary>{question}<span className={styles.faqIcon}><Plus size={17} aria-hidden="true" /></span></summary>
              <p>{answer}</p>
            </details>
          ))}</div>
        </section>

      </main>

      <footer className={`${styles.shell} ${styles.footer}`} data-landing-reveal>
        <Brand />
        <nav aria-label="Navigasi footer">
          <a href={telegram}>Telegram</a>
          <a href="#tillfold-landing">Kembali ke atas</a>
        </nav>
      </footer>
    </div>
  );
}
