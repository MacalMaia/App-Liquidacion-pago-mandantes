import Header from "./components/Header";
import Liquidador from "./pages/Liquidador";

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Header />
      <main className="flex-1">
        <Liquidador />
      </main>
    </div>
  );
}
