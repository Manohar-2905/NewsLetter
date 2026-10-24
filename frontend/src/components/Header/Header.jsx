import React, { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { Menu, X, Zap } from 'lucide-react'
import { Container, Logo } from '../index'
import { useAgent } from '../../contexts'

function Header() {
  const navigate = useNavigate()
  const { run, isRunning } = useAgent()
  const [menuOpen, setMenuOpen] = useState(false)

  const waitingForApproval = run?.status === 'awaiting_approval'

  const navItems = [
    {
      name: 'Home',
      slug: '/',
      active: true,
    },
    {
      name: 'How it works',
      slug: '/#how-it-works',
      active: true,
    },
    {
      name: 'Agent',
      slug: '/agent',
      active: true,
    },
    {
      name: 'Runs',
      slug: '/runs',
      active: true,
    },
  ]

  return (
    <header className='sticky top-0 z-50 border-b border-white/5 bg-jet/80 backdrop-blur-md'>
      <Container>
        <nav className='flex items-center h-16'>
          <Link to='/' className='mr-6' onClick={() => setMenuOpen(false)}>
            <Logo />
          </Link>

          <ul className='hidden md:flex items-center gap-1 ml-auto'>
            {navItems.map((item) =>
              item.active ? (
                <li key={item.name}>
                  <NavLink
                    to={item.slug}
                    end={item.slug === '/'}
                    className={({ isActive }) =>
                      `px-4 py-2 rounded-full text-sm duration-200 ${
                        isActive && !item.slug.includes('#')
                          ? 'text-white bg-white/10'
                          : 'text-neutral-400 hover:text-white hover:bg-white/5'
                      }`
                    }
                  >
                    {item.name}
                  </NavLink>
                </li>
              ) : null
            )}
          </ul>

          <div className='flex items-center gap-2 ml-auto md:ml-4'>
            {(isRunning || waitingForApproval) && (
              <button
                onClick={() => navigate('/agent')}
                className='hidden sm:inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs border border-rose/40 text-rose-300 hover:bg-rose/10 duration-200'
              >
                <span className='size-2 rounded-full bg-rose animate-pulse-soft' />
                {waitingForApproval ? 'Draft needs approval' : 'Agent running'}
              </button>
            )}
            <button
              onClick={() => navigate('/agent')}
              className='hidden sm:inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-semibold bg-rose text-jet hover:bg-rose-400 duration-200'
            >
              <Zap size={15} />
              Launch agent
            </button>
            <button
              className='md:hidden p-2 rounded-lg text-neutral-300 hover:bg-white/5'
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((prev) => !prev)}
            >
              {menuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </nav>

        {menuOpen && (
          <ul className='md:hidden pb-4 space-y-1'>
            {navItems.map((item) => (
              <li key={item.name}>
                <button
                  onClick={() => {
                    setMenuOpen(false)
                    navigate(item.slug)
                  }}
                  className='w-full text-left px-3 py-2 rounded-lg text-sm text-neutral-300 hover:bg-white/5'
                >
                  {item.name}
                </button>
              </li>
            ))}
          </ul>
        )}
      </Container>
    </header>
  )
}

export default Header
