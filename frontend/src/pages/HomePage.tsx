import academyLogo from '../assets/placeholderLogo.png'

export default function HomePage() {
  return (
    <section className="home-page-enter flex min-h-[calc(100vh-3rem)] flex-col items-center justify-center gap-6 text-center">
      <img
        src={academyLogo}
        alt="VK Cricket Academy logo"
        className="h-32 w-32 object-contain sm:h-40 sm:w-40"
      />
      <h1 className="max-w-3xl text-3xl font-bold tracking-tight text-slate-900 sm:text-5xl">
        Welcome to VK Cricket Academy!
      </h1>
    </section>
  )
}
