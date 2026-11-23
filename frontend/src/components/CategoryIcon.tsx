import {
  Banknote, Bolt, Car, Dumbbell, Droplet, Gift, GraduationCap, Home,
  MedicalCross, Parking, ShoppingBag, Tag, Utensils, Wallet, Wifi,
} from "./icons";

/** Category identity is separate from the direction shown by its label and amount. */
export function CategoryIcon({ name, type }: { name: string; type: string }) {
  const value = name.toLocaleLowerCase("id-ID");
  const Icon = /bonus|hadiah|hibah/.test(value) ? Gift
    : type === "income" ? Banknote
    : /parkir|parking/.test(value) ? Parking
    : /makan|minum|jajan|kopi|kuliner|restoran/.test(value) ? Utensils
    : /galon|\bair\b|pdam/.test(value) ? Droplet
    : /listrik|pln/.test(value) ? Bolt
    : /internet|pulsa|kuota|wifi|telepon/.test(value) ? Wifi
    : /gym|fitnes|olahraga/.test(value) ? Dumbbell
    : /transport|bensin|bbm|ojek|taksi|kendaraan/.test(value) ? Car
    : /kesehatan|obat|dokter|medis/.test(value) ? MedicalCross
    : /pendidikan|sekolah|kuliah|kursus|buku/.test(value) ? GraduationCap
    : /rumah|sewa|kos\b|kontrakan/.test(value) ? Home
    : /belanja|shopping|pakaian/.test(value) ? ShoppingBag
    : /tabungan|investasi/.test(value) ? Wallet
    : Tag;
  return <Icon className="size-5" />;
}
