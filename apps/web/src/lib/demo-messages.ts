// The demo dataset's scripted customer messages (services/api/seed/README.md). They fill the form
// so the five demo scenarios can be run with one click. Every name and number is fictional.

export interface DemoMessage {
  id: string;
  label: string;
  hint: string;
  phone: string;
  text: string;
  hero?: boolean;
}

export const DEMO_MESSAGES: DemoMessage[] = [
  {
    id: "repeat-ac",
    label: "Repeat AC complaint",
    hint: "Ravi Kumar · LG AC serviced twice",
    phone: "90000 20001",
    text: "Bhaiya LG AC phir se thanda nahi kar raha. Kal 5 ke baad aa sakte ho?",
    hero: true,
  },
  {
    id: "two-acs",
    label: "Which AC?",
    hint: "Meena Iyer owns two",
    phone: "90000 20003",
    text: "AC thanda nahi kar raha",
  },
  {
    id: "lg-ac",
    label: "The LG one",
    hint: "Same customer, brand named",
    phone: "90000 20003",
    text: "LG AC not cooling properly",
  },
  {
    id: "new-customer",
    label: "Unknown customer",
    hint: "Deepak, not on file",
    phone: "90000 29999",
    text: "Namaste, mera naam Deepak hai. Mere Godrej fridge ka compressor start nahi ho raha. Indiranagar mein hoon. Kal aa sakte ho?",
  },
  {
    id: "safety",
    label: "Safety-critical",
    hint: "Farhan Qureshi's fridge",
    phone: "90000 20004",
    text: "Fridge se chingari nikal rahi hai aur jalne ki smell aa rahi hai",
  },
];
