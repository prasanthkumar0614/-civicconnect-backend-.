"""
core/management/commands/add_all_real_mandals.py

Adds REAL mandal names for every Andhra Pradesh district, sourced from the
official district reorganization notifications (compiled via Wikipedia's
"List of mandals of Andhra Pradesh", which cites the AP govt's 2022-2025
notifications and the state's 2022-23 Socio Economic Survey).

Covers 28 districts total — note AP has been 28 districts since Dec 2025,
not 26: Polavaram and Markapuram were newly carved out. This command will
CREATE these 2 as new districts automatically if they're missing.

This command is ADDITIVE and SAFE to re-run: it uses get_or_create, so it
never duplicates a mandal that's already there. It does NOT delete any
existing placeholder mandals (e.g. "Mandal 1", "Mandal 2") — if you want
those removed, run with --replace to delete a district's existing mandals
before adding the real ones.

Usage:
    python manage.py add_all_real_mandals            # add-only, safe
    python manage.py add_all_real_mandals --replace   # wipe + replace mandals per district
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Area

DISTRICT_DATA = [
    {
        "aliases": ["Alluri Sitharama Raju", "Alluri Seetarama Raju", "Alluri Seetharama Raju", "ASR"],
        "mandals": ["Ananthagiri", "Araku Valley", "Chintapalle", "Dumbriguda", "G. Madugula",
                    "Gudem Kotha Veedhi", "Hukumpeta", "Koyyuru", "Munchingi Puttu", "Paderu", "Peda Bayalu"],
    },
    {
        "aliases": ["Anakapalli"],
        "mandals": ["Atchutapuram", "Elamanchili", "Kotauratla", "Nakkapalle", "Payakaraopeta",
                    "Rambilli", "Sarvasiddhi Rayavaram", "Anakapalli", "Butchayyapeta", "Cheedikada",
                    "Chodavaram", "Devarapalli", "K. Kotapadu", "Kasimkota", "Munagapaka", "Paravada",
                    "Sabbavaram", "Golugonda", "Madugula", "Makavarapalem", "Narsipatnam",
                    "Nathavaram", "Ravikamatham", "Rolugunta"],
    },
    {
        "aliases": ["Ananthapuramu", "Anantapuramu", "Anantapur"],
        "mandals": ["Anantapuramu", "Atmakur", "Bukkaraya Samudram", "Garladinne", "Kudair",
                    "Narpala", "Peddapappur", "Putlur", "Raptadu", "Singanamala", "Tadipatri",
                    "Yellanur", "Gooty", "Guntakal", "Pamidi", "Peddavadugur", "Uravakonda",
                    "Vajrakarur", "Vidapanakal", "Yadiki", "Beluguppa", "Bommanahal",
                    "Brahmasamudram", "D.Hirehal", "Gummagatta", "Kalyandurg", "Kambadur",
                    "Kanekal", "Kundurpi", "Rayadurg", "Settur"],
    },
    {
        "aliases": ["Annamayya", "Annamaiah"],
        "mandals": ["Beerangi Kothakota", "Chowdepalle", "Kurabalakota", "Madanapalle",
                    "Mulakalacheruvu", "Nimmanapalle", "Peddamandyam", "Peddathippasamudram",
                    "Punganur", "Ramasamudram", "Thamballapalle", "Gurramkonda", "Kalakada",
                    "Kalikiri", "Kambhamvaripalle", "Pileru", "Sodam", "Somala", "Vayalpad",
                    "Chinnamandyam", "Galiveedu", "Lakkireddipalli", "Ramapuram", "Rayachoti",
                    "Sambepalli"],
    },
    {
        "aliases": ["Bapatla"],
        "mandals": ["Bapatla", "Karlapalem", "Martur", "Parchur", "Pittalavanipalem", "Yeddanapudi",
                    "Chinaganjam", "Chirala", "Inkollu", "Karamchedu", "Vetapalem", "Amruthalur",
                    "Bhattiprolu", "Cherukupalle", "Kolluru", "Nagaram", "Nizampatnam", "Repalle",
                    "Tsundur", "Vemuru"],
    },
    {
        "aliases": ["Chittoor"],
        "mandals": ["Bangarupalem", "Chittoor", "Chittoor Urban", "Gangadhara Nellore", "Gudipala",
                    "Irala", "Penumuru", "Pulicherla", "Puthalapattu", "Rompicherla",
                    "Sri Rangaraja Puram", "Thavanampalle", "Vedurukuppam", "Yadamarri", "Kuppam",
                    "Ramakuppam", "Santhipuram", "Gudipalle", "Nagari", "Nindra", "Palasamudram",
                    "Vijayapuram", "Karvetinagar", "Baireddipalle", "Gangavaram", "Palamaner",
                    "Peddapanjani", "Venkatagirikota"],
    },
    {
        "aliases": ["Dr. B. R. Ambedkar Konaseema", "Konaseema", "Dr B R Ambedkar Konaseema"],
        "mandals": ["Allavaram", "Amalapuram", "I. Polavaram", "Katrenikona", "Malikipuram",
                    "Mamidikuduru", "Mummidivaram", "Razole", "Sakhinetipalle", "Uppalaguptam",
                    "Ainavilli", "Alamuru", "Ambajipeta", "Atreyapuram", "Kothapeta",
                    "P. Gannavaram", "Ravulapalem", "K. Gangavaram", "Ramachandrapuram"],
    },
    {
        "aliases": ["East Godavari"],
        "mandals": ["Chagallu", "Devarapalle", "Gopalapuram", "Kovvur", "Nallajerla", "Nidadavole",
                    "Peravali", "Tallapudi", "Undrajavaram", "Anaparthi", "Biccavolu", "Gokavaram",
                    "Kadiam", "Kapileswarapuram", "Korukonda", "Mandapeta", "Rajahmundry Urban",
                    "Rajahmundry Rural", "Rajanagaram", "Rangampeta", "Rayavaram", "Seethanagaram"],
    },
    {
        "aliases": ["Eluru"],
        "mandals": ["Bhimadole", "Denduluru", "Eluru", "Kaikalur", "Kalidindi", "Mandavalli",
                    "Mudinepalle", "Nidamarru", "Pedapadu", "Pedavegi", "Unguturu", "Buttayagudem",
                    "Dwaraka Tirumala", "Jangareddygudem", "Jeelugu Milli", "Kamavarapukota",
                    "Koyyalagudem", "Kukunoor", "Polavaram", "T. Narasapuram", "Velairpadu",
                    "Agiripalli", "Chatrai", "Chintalapudi", "Lingapalem", "Musunuru", "Nuzvid"],
    },
    {
        "aliases": ["Guntur"],
        "mandals": ["Guntur East", "Guntur West", "Medikonduru", "Pedakakani", "Pedanandipadu",
                    "Phirangipuram", "Prathipadu", "Tadikonda", "Thullur", "Vatticherukuru",
                    "Chebrolu", "Duggirala", "Kakumanu", "Kollipara", "Mangalagiri", "Ponnur",
                    "Tadepalli", "Tenali"],
    },
    {
        "aliases": ["Kakinada"],
        "mandals": ["Gollaprolu", "Kajuluru", "Kakinada Rural", "Kakinada Urban", "Karapa",
                    "Kothapalle", "Pedapudi", "Pithapuram", "Thallarevu", "Gandepalle", "Jaggampeta",
                    "Kirlampudi", "Kotananduru", "Peddapuram", "Prathipadu", "Rowthulapudi",
                    "Samalkota", "Sankhavaram", "Thondangi", "Tuni", "Yeleswaram"],
    },
    {
        "aliases": ["Krishna"],
        "mandals": ["Bapulapadu", "Gannavaram", "Gudivada", "Gudlavalleru", "Nandivada",
                    "Pedaparupudi", "Unguturu", "Avanigadda", "Bantumilli", "Challapalli",
                    "Ghantasala", "Guduru", "Koduru", "Kruthivennu", "Machilipatnam", "Mopidevi",
                    "Nagayalanka", "Pedana", "Kankipadu", "Movva", "Pamarru", "Pamidimukkala",
                    "Penamaluru", "Thotlavalluru", "Vuyyuru"],
    },
    {
        "aliases": ["Kurnool"],
        "mandals": ["Adoni Urban", "Adoni Rural", "Gonegandla", "Holagunda", "Kosigi", "Kowthalam",
                    "Mantralayam", "Nandavaram", "Pedda Kadubur", "Yemmiganur", "C.Belagal", "Gudur",
                    "Kallur", "Kodumur", "Kurnool Urban", "Kurnool Rural", "Orvakal", "Veldurthi",
                    "Alur", "Aspari", "Chippagiri", "Devanakonda", "Halaharvi", "Krishnagiri",
                    "Maddikera East", "Pattikonda", "Tuggali"],
    },
    {
        "aliases": ["Markapuram"], "create_if_missing": True,  # new district, split from Prakasam (Dec 2025)
        "mandals": ["Chandra Sekhara Puram", "Hanumanthuni Padu", "Kanigiri", "Pamur",
                    "Pedacherlo Palle", "Veligandla", "Ardhaveedu", "Bestawaripeta", "Cumbum",
                    "Dornala", "Giddalur", "Konakanamitla", "Komarolu", "Markapuram",
                    "Peda Araveedu", "Pullalacheruvu", "Podili", "Racherla", "Tarlupadu",
                    "Tripuranthakam", "Yerragondapalem"],
    },
    {
        "aliases": ["Nandyal", "Nandyala"],
        "mandals": ["Atmakur", "Bandi Atmakur", "Jupadu Bungalow", "Kothapalle", "Midthuru",
                    "Nandikotkur", "Pagidyala", "Pamulapadu", "Srisailam", "Velgodu",
                    "Banaganapalle", "Koilkuntla", "Kolimigundla", "Owk", "Sanjamala",
                    "Bethamcherla", "Dhone", "Peapally", "Allagadda", "Chagalamarri", "Dornipadu",
                    "Gadivemula", "Gospadu", "Mahanandi", "Nandyal Rural", "Nandyal Urban",
                    "Panyam", "Rudravaram", "Sirivella", "Uyyalawada"],
    },
    {
        "aliases": ["NTR"],
        "mandals": ["Chandarlapadu", "Jaggayyapeta", "Kanchikacherla", "Nandigama",
                    "Penuganchiprolu", "Vatsavai", "Veerullapadu", "A. Konduru", "Gampalagudem",
                    "Reddigudem", "Tiruvuru", "Vissannapeta", "G.Konduru", "Ibrahimpatnam",
                    "Mylavaram", "Vijayawada Rural", "Vijayawada North", "Vijayawada Central",
                    "Vijayawada East", "Vijayawada West"],
    },
    {
        "aliases": ["Palnadu"],
        "mandals": ["Dachepalle", "Durgi", "Gurazala", "Karempudi", "Macherla", "Machavaram",
                    "Piduguralla", "Rentachintala", "Veldurthi", "Bollapalle", "Chilakaluripet",
                    "Edlapadu", "Ipuru", "Nadendla", "Narasaraopet", "Nuzendla", "Rompicherla",
                    "Savalyapuram", "Vinukonda", "Amaravathi", "Atchampet", "Bellamkonda",
                    "Krosuru", "Muppalla", "Nekarikallu", "Pedakurapadu", "Rajupalem",
                    "Sattenapalle"],
    },
    {
        "aliases": ["Parvathipuram Manyam", "Manyam", "Parvathipuram"],
        "mandals": ["Bhamini", "Gummalakshmipuram", "Jiyyammavalasa", "Kurupam", "Palakonda",
                    "Seethampeta", "Veeraghattam", "Balijipeta", "Garugubilli", "Komarada",
                    "Makkuva", "Pachipenta", "Parvathipuram", "Salur", "Seethanagaram"],
    },
    {
        "aliases": ["Polavaram"], "create_if_missing": True,  # new district, split from ASR/East Godavari (Dec 2025)
        "mandals": ["Chintur", "Etapaka", "Kunavaram", "Vararamachandrapuram", "Addateegala",
                    "Devipatnam", "Gangavaram", "Gurthedu", "Maredumilli", "Rajavommangi",
                    "Rampachodavaram", "Y. Ramavaram"],
    },
    {
        "aliases": ["Prakasam"],
        "mandals": ["Korisapadu", "J. Panguluru", "Addanki", "Ballikurava", "Santhamaguluru",
                    "Mundlamuru", "Ongole", "Thallur", "Darsi", "Donakonda", "Kanigiri",
                    "Kurichedu", "Gudluru", "Kandukuru", "Lingasamudram", "Ulavapadu",
                    "Marripudi", "Ponnaluru", "Voletivaripalem", "Chimakurthi", "Kondapi",
                    "Kotha Patnam", "Maddipadu", "Naguluppalapadu", "Ongole Urban",
                    "Ongole Rural", "Santhanuthala Padu", "Singarayakonda", "Tangutur",
                    "Zarugumilli"],
    },
    {
        "aliases": ["Sri Potti Sriramulu Nellore", "Sri Potti Sri Ramulu Nellore", "Nellore", "SPSR Nellore"],
        "mandals": ["Ananthasagaram", "Anumasamudrampeta", "Atmakur", "Chejerla", "Kaluvoya",
                    "Marripadu", "Sangam", "Sitarampuramu", "Udayagiri", "Gudur", "Chillakur",
                    "Kota", "Allur", "Bogolu", "Dagadarthi", "Duttaluru", "Jaladanki", "Kaligiri",
                    "Kavali", "Kodavaluru", "Vidavaluru", "Vinjamuru", "Buchireddypalem",
                    "Indukurpet", "Kovur", "Manubolu", "Muttukuru", "Nellore Urban",
                    "Nellore Rural", "Podalakuru", "Rapuru", "Saidapuramu", "Thotapalligudur",
                    "Venkatachalam"],
    },
    {
        "aliases": ["Sri Sathya Sai", "Sri Satyasai", "Satya Sai"],
        "mandals": ["Bathalapalle", "Chennekothapalle", "Dharmavaram", "Kanaganapalle",
                    "Mudigubba", "Ramagiri", "Tadimarri", "Gandlapenta", "Kadiri", "Lepakshi",
                    "Nallacheruvu", "Nambulapulakunta", "Tanakal", "Agali", "Amarapuram",
                    "Gudibanda", "Madakasira", "Rolla", "Chilamathur", "Gorantla", "Hindupur",
                    "Parigi", "Penukonda", "Roddam", "Somandepalle", "Talupula", "Amadagur",
                    "Bukkapatnam", "Kothacheruvu", "Nallamada", "Obuladevaracheruvu",
                    "Puttaparthi"],
    },
    {
        "aliases": ["Srikakulam"],
        "mandals": ["Ichchapuram", "Kanchili", "Kaviti", "Mandasa", "Palasa", "Sompeta",
                    "Vajrapukothuru", "Amadalavalasa", "Burja", "Etcherla", "Ganguvarisigadam",
                    "Gara", "Jalumuru", "Laveru", "Narasannapeta", "Polaki", "Ponduru",
                    "Ranastalam", "Sarubujjili", "Srikakulam", "Hiramandalam", "Kotabommali",
                    "Kothuru", "Lakshminarsupeta", "Meliaputti", "Nandigam", "Pathapatnam",
                    "Santhabommali", "Saravakota", "Tekkali"],
    },
    {
        "aliases": ["Tirupati", "Sri Balaji"],
        "mandals": ["Balayapalle", "Dakkili", "K. V. B. Puram", "Nagalapuram", "Narayanavanam",
                    "Pichatur", "Renigunta", "Srikalahasti", "Thottambedu", "Venkatagiri",
                    "Yerpedu", "Buchinaidu Kandriga", "Chittamur", "Doravarisatram", "Naidupeta",
                    "Ozili", "Pellakur", "Satyavedu", "Sullurpeta", "Tada", "Vakadu",
                    "Varadaiahpalem", "Chandragiri", "Chinnagottigallu", "Chitvel", "Kodur",
                    "Obulavaripalle", "Pakala", "Penagalur", "Pullampeta", "Puttur",
                    "Ramachandrapuram", "Tirupati Rural", "Tirupati Urban", "Vadamalapeta",
                    "Yerravaripalem"],
    },
    {
        "aliases": ["Visakhapatnam"],
        "mandals": ["Anandapuram", "Bheemunipatnam", "Padmanabham", "Seethammadhara",
                    "Visakhapatnam Rural", "Gajuwaka", "Gopalapatnam", "Maharanipeta", "Mulagada",
                    "Pedagantyada", "Pendurthi"],
    },
    {
        "aliases": ["Vizianagaram"],
        "mandals": ["Badangi", "Bobbili", "Dattirajeru", "Gajapathinagaram", "Mentada",
                    "Ramabhadrapuram", "Therlam", "Cheepurupalle", "Garividi", "Gurla",
                    "Merakamudidam", "Rajam", "Regidi Amadalavalasa", "Santhakaviti", "Vangara",
                    "Bhogapuram", "Bondapalle", "Denkada", "Gantyada", "Jami", "Kothavalasa",
                    "Lakkavarapukota", "Nellimarla", "Pusapatirega", "Srungavarapukota", "Vepada",
                    "Vizianagaram"],
    },
    {
        "aliases": ["West Godavari"],
        "mandals": ["Akividu", "Bhimavaram", "Kalla", "Palacoderu", "Undi", "Veeravasaram",
                    "Achanta", "Mogalthur", "Palakollu", "Penugonda", "Penumantra", "Poduru",
                    "Yelamanchili", "Attili", "Ganapavaram", "Iragavaram", "Pentapadu",
                    "Tadepalligudem", "Tanuku"],
    },
    {
        "aliases": ["YSR Kadapa", "Kadapa", "Y.S.R.", "YSR"],
        "mandals": ["Atlur", "B. Kodur", "Badvel", "Brahmamgarimattam", "Chapad", "Duvvur",
                    "Gopavaram", "Kalasapadu", "Khajipet", "Porumamilla", "S.Mydukur",
                    "Sri Avadhutha Kasinayana", "Jammalamadugu", "Kondapuram", "Muddanur",
                    "Mylavaram", "Peddamudium", "Proddatur", "Rajupalem", "Chennur",
                    "Chinthakommadinne", "Kadapa", "Kamalapuram", "Pendlimarri", "Sidhout",
                    "Vallur", "Vontimitta", "Yerraguntla", "Chakrayapet", "Lingala", "Pulivendla",
                    "Simhadripuram", "Thondur", "Veerapunayunipalle", "Vempalle", "Vemula",
                    "Nandalur", "Rajampet", "T. Sundupalle", "Veeraballi"],
    },
]


class Command(BaseCommand):
    help = "Adds real mandal names for all 28 AP districts (sourced from official govt notifications)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--replace", action="store_true",
            help="Delete a district's existing mandals before adding the real ones (use with caution).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        replace = options["replace"]
        matched_count = 0
        unmatched = []
        total_mandals_created = 0

        for entry in DISTRICT_DATA:
            district = None
            for alias in entry["aliases"]:
                district = Area.objects.filter(
                    level=Area.Level.DISTRICT, name__iexact=alias
                ).first()
                if district:
                    break

            if not district:
                if entry.get("create_if_missing"):
                    district = Area.objects.create(
                        name=entry["aliases"][0], level=Area.Level.DISTRICT, parent=None,
                    )
                    self.stdout.write(self.style.SUCCESS(f"  Created new district: {district.name}"))
                else:
                    unmatched.append(entry["aliases"][0])
                    continue

            matched_count += 1

            if replace:
                Area.objects.filter(parent=district, level=Area.Level.MANDAL).delete()

            created_here = 0
            for mandal_name in entry["mandals"]:
                _, created = Area.objects.get_or_create(
                    name=mandal_name, level=Area.Level.MANDAL, parent=district,
                )
                if created:
                    created_here += 1

            total_mandals_created += created_here
            self.stdout.write(f"  {district.name}: {created_here} real mandals added")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Matched {matched_count}/{len(DISTRICT_DATA)} districts, "
            f"created {total_mandals_created} new mandal records."
        ))

        if unmatched:
            self.stdout.write(self.style.WARNING(
                f"\nCould NOT find these districts in your database (check spelling/aliases): "
                f"{', '.join(unmatched)}\n"
                f"Tell me your exact stored name for each and I'll add it as an alias."
            ))
