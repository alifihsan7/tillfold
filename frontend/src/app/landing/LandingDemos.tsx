"use client";

import { useState, type CSSProperties } from "react";
import Image from "next/image";
import { BarChart2, Send } from "@/components/icons";
import styles from "./landing.module.css";

const money = new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 });
const paydayTotal = 2_400_000;
const sampleExpenses = [66_000, 104_000, 54_000, 128_000, 78_000, 46_000, 96_000];

export function ChatDemo() {
  const [sent, setSent] = useState(false);

  return (
    <figure className={`${styles.demo} ${styles.chat}`}>
      <figcaption><Image src="/tillfold.svg" width={22} height={22} alt="" unoptimized /> <strong>Tillfold</strong><span>Simulasi chat</span></figcaption>
      <blockquote>kopi 25k mandiri</blockquote>
      <div className={styles.chatStatus} aria-live="polite">
        {sent && <div className={styles.chatReceipt}><span>Pengeluaran tercatat</span><strong>Rp25.000</strong><span>Kopi · Mandiri</span></div>}
      </div>
      <button className={styles.demoAction} type="button" onClick={() => setSent((previous) => !previous)}>
        {!sent && <Send size={15} aria-hidden="true" />}
        {sent ? "Ulangi simulasi" : "Kirim contoh"}
      </button>
    </figure>
  );
}

export function PaydayDemo() {
  const [daily, setDaily] = useState(40);
  const allocation = [
    { name: "Uang harian", share: daily, color: "blue" },
    { name: "Tagihan", share: 25, color: "green" },
    { name: "Target tabungan", share: 20, color: "violet" },
    { name: "Dana darurat", share: 55 - daily, color: "sand" },
  ] as const;

  return (
    <figure className={`${styles.demo} ${styles.payday}`}>
      <figcaption><strong>Pembagian gaji</strong><span>Contoh alokasi</span></figcaption>
      <p className={styles.total}>{money.format(paydayTotal)}</p>
      <div className={styles.paydayBar} aria-hidden="true">
        {allocation.map(({ name, color, share }) => <span key={name} className={styles[color]} style={{ flexGrow: share }} />)}
      </div>
      <ul>{allocation.map(({ name, color, share }) => (
        <li key={name}><span className={styles[color]} aria-hidden="true" /><span>{name}</span><strong key={share}>{money.format(paydayTotal * share / 100)}</strong></li>
      ))}</ul>
      <div className={styles.allocationAdjust}>
        <label htmlFor="demo-payday-share">Porsi uang harian</label>
        <output htmlFor="demo-payday-share"><span key={daily}>{daily}%</span></output>
        <input id="demo-payday-share" type="range" min={30} max={50} step={5} value={daily}
          style={{ "--payday-progress": `${(daily - 30) * 5}%` } as CSSProperties}
          aria-valuetext={`${daily} persen`} onChange={(event) => setDaily(event.currentTarget.valueAsNumber)} />
      </div>
    </figure>
  );
}

export function ReportDemo() {
  const [selected, setSelected] = useState(3);

  return (
    <figure className={`${styles.demo} ${styles.report}`}>
      <figcaption><strong>Arus kas harian</strong><BarChart2 size={18} aria-hidden="true" /></figcaption>
      <div className={styles.reportBars} role="group" aria-label="Contoh pengeluaran harian">
        {sampleExpenses.map((amount, index) => (
          <button key={index} type="button" aria-pressed={selected === index}
            aria-label={`${index + 4} Mei, ${money.format(amount)}`} onClick={() => setSelected(index)}>
            <span style={{ height: `${amount / 1_500}%`, animationDelay: `${index * 38}ms` }} aria-hidden="true" />
            <small>{index + 4}</small>
          </button>
        ))}
      </div>
      <div className={styles.selectedDay} aria-live="polite">
        <div><span key={selected}>{selected + 4} Mei</span><strong>Pengeluaran</strong></div>
        <strong key={selected}>{money.format(sampleExpenses[selected])}</strong>
      </div>
    </figure>
  );
}
