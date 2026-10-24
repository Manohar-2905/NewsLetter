import React, { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { CallToAction, CostSection, FeatureGrid, Hero, ModesSection, StatsStrip, WorkflowSection } from '../components'

function Home() {
  const { hash } = useLocation()

  // Support links like "/#how-it-works" from the header.
  useEffect(() => {
    if (!hash) return
    const section = document.getElementById(hash.slice(1))
    section?.scrollIntoView({ behavior: 'smooth' })
  }, [hash])

  return (
    <>
      <Hero />
      <StatsStrip />
      <WorkflowSection />
      <FeatureGrid />
      <ModesSection />
      <CostSection />
      <CallToAction />
    </>
  )
}

export default Home
