import React from 'react'
import { Link } from 'react-router-dom'
import { Container, Logo } from '../index'

function Footer() {
  const footerLinks = [
    { name: 'Home', slug: '/' },
    { name: 'Agent', slug: '/agent' },
    { name: 'Runs', slug: '/runs' },
  ]

  return (
    <footer className='border-t border-white/5 bg-jet-800'>
      <Container className='py-8 flex flex-col md:flex-row gap-6 md:items-center justify-between'>
        <div className='space-y-2 max-w-md'>
          <Logo width='28px' />
          <p className='text-xs text-neutral-500'>
            Summaries are AI-generated from linked sources. Always verify important facts in the original articles.
            Sending is simulated; no email is delivered.
          </p>
        </div>
        <ul className='flex gap-6 text-sm'>
          {footerLinks.map((link) => (
            <li key={link.name}>
              <Link to={link.slug} className='text-neutral-400 hover:text-cerulean-300 duration-200'>
                {link.name}
              </Link>
            </li>
          ))}
        </ul>
      </Container>
    </footer>
  )
}

export default Footer
