import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Compass } from 'lucide-react'
import { Button, Container, EmptyState } from '../components'

function NotFound() {
  const navigate = useNavigate()

  return (
    <Container className='py-24'>
      <EmptyState icon={Compass} title='Page not found' text="This page doesn't exist. Let's get you back on track.">
        <Button variant='accent' onClick={() => navigate('/')}>
          Go home
        </Button>
      </EmptyState>
    </Container>
  )
}

export default NotFound
