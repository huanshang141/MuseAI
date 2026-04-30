import { describe, it, expect, beforeEach, vi } from 'vitest'

vi.mock('../../api/index.js', () => ({
  api: {
    tour: {
      createSession: vi.fn(),
      getSession: vi.fn(),
      updateSession: vi.fn(),
      recordEvents: vi.fn(),
      getEvents: vi.fn(),
      completeHall: vi.fn(),
      generateReport: vi.fn(),
      getReport: vi.fn(),
      chatStream: vi.fn(),
      getHalls: vi.fn(),
    },
    exhibits: {
      list: vi.fn(),
    },
  },
}))

vi.mock('../useAuth.js', () => ({
  useAuth: () => ({
    isAuthenticated: { value: false },
  }),
}))

import { api } from '../../api/index.js'

describe('useTour', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    vi.resetModules()
  })

  it('starts with default state', async () => {
    const { useTour } = await import('../useTour.js')
    const { tourSession, tourStep, currentHall, currentExhibit, loading, error, tourReport, halls } = useTour()

    expect(tourSession.value).toBeNull()
    expect(tourStep.value).toBe('onboarding')
    expect(currentHall.value).toBeNull()
    expect(currentExhibit.value).toBeNull()
    expect(loading.value).toEqual({ session: false, chat: false, report: false })
    expect(error.value).toBeNull()
    expect(tourReport.value).toBeNull()
    expect(halls.value).toEqual([])
  })

  it('createTourSession calls API and updates state', async () => {
    const mockSession = {
      id: 'session-1',
      session_token: 'token-abc',
      interest_type: 'A',
      persona: 'A',
      assumption: 'A',
      status: 'onboarding',
    }
    api.tour.createSession.mockResolvedValueOnce({ ok: true, data: mockSession })

    const { useTour } = await import('../useTour.js')
    const { createTourSession, tourSession, sessionToken } = useTour()

    const result = await createTourSession('A', 'A', 'A')

    expect(api.tour.createSession).toHaveBeenCalledWith({
      interest_type: 'A',
      persona: 'A',
      assumption: 'A',
      guest_id: expect.stringMatching(/^guest-/),
    })
    expect(tourSession.value).toEqual(mockSession)
    expect(sessionToken.value).toBe('token-abc')
    expect(localStorage.getItem('tour_session_id')).toBe('session-1')
  })

  it('createTourSession handles API error', async () => {
    api.tour.createSession.mockResolvedValueOnce({
      ok: false,
      data: { detail: 'Server error' },
    })

    const { useTour } = await import('../useTour.js')
    const { createTourSession, error } = useTour()

    const result = await createTourSession('A', 'A', 'A')

    expect(result).toBeNull()
    expect(error.value).toBe('Server error')
  })

  it('restoreSession recovers from localStorage', async () => {
    localStorage.setItem('tour_session_id', 'stored-id')
    localStorage.setItem('tour_session_token', 'stored-token')

    api.tour.getSession.mockResolvedValueOnce({
      ok: true,
      data: { id: 'stored-id', status: 'touring', current_hall: 'relic-hall' },
    })
    api.exhibits.list.mockResolvedValueOnce({ ok: true, data: { exhibits: [] } })

    const { useTour } = await import('../useTour.js')
    const { restoreSession, tourStep, currentHall } = useTour()

    const result = await restoreSession()

    expect(result).toBe(true)
    expect(tourStep.value).toBe('tour')
    expect(currentHall.value).toBe('relic-hall')
    expect(api.tour.getSession).toHaveBeenCalledWith('stored-id', 'stored-token')
  })

  it('restoreSession clears storage on API error', async () => {
    localStorage.setItem('tour_session_id', 'bad-id')
    localStorage.setItem('tour_session_token', 'bad-token')

    api.tour.getSession.mockResolvedValueOnce({ ok: false })

    const { useTour } = await import('../useTour.js')
    const { restoreSession } = useTour()

    const result = await restoreSession()

    expect(result).toBe(false)
    expect(localStorage.getItem('tour_session_id')).toBeNull()
    expect(localStorage.getItem('tour_session_token')).toBeNull()
  })

  it('restoreSession goes to report when completed', async () => {
    localStorage.setItem('tour_session_id', 'completed-id')
    localStorage.setItem('tour_session_token', 'completed-token')

    api.tour.getSession.mockResolvedValueOnce({
      ok: true,
      data: { id: 'completed-id', status: 'completed' },
    })

    const { useTour } = await import('../useTour.js')
    const { restoreSession, tourStep } = useTour()

    await restoreSession()

    expect(tourStep.value).toBe('report')
  })

  it('fetchHalls updates halls state', async () => {
    const mockHalls = [
      { slug: 'relic-hall', name: '出土文物展厅' },
      { slug: 'site-hall', name: '遗址保护大厅' },
    ]
    api.tour.getHalls.mockResolvedValueOnce({ ok: true, data: { halls: mockHalls } })

    const { useTour } = await import('../useTour.js')
    const { fetchHalls, halls } = useTour()

    await fetchHalls()

    expect(halls.value).toEqual(mockHalls)
  })

  it('selectHall updates currentHall and calls API', async () => {
    const { useTour } = await import('../useTour.js')
    const { createTourSession, selectHall, currentHall, tourSession } = useTour()

    api.tour.createSession.mockResolvedValueOnce({
      ok: true,
      data: { id: 's1', session_token: 't1', status: 'onboarding' },
    })
    await createTourSession('A', 'A', 'A')

    api.tour.updateSession.mockResolvedValueOnce({ ok: true })
    api.exhibits.list.mockResolvedValueOnce({ ok: true, data: { exhibits: [] } })

    await selectHall('relic-hall')

    expect(currentHall.value).toBe('relic-hall')
    expect(api.tour.updateSession).toHaveBeenCalledWith(
      's1',
      { current_hall: 'relic-hall', status: 'touring' },
      't1',
    )
  })

  it('bufferEvent persists to localStorage', async () => {
    const { useTour } = await import('../useTour.js')
    const { createTourSession, bufferEvent, selectHall, tourSession } = useTour()

    api.tour.createSession.mockResolvedValueOnce({
      ok: true,
      data: { id: 's1', session_token: 't1', status: 'onboarding' },
    })
    await createTourSession('A', 'A', 'A')

    api.tour.updateSession.mockResolvedValueOnce({ ok: true })
    api.exhibits.list.mockResolvedValueOnce({ ok: true, data: { exhibits: [] } })
    await selectHall('relic-hall')

    bufferEvent('hall_enter', {})

    const stored = JSON.parse(localStorage.getItem('tour_pending_events') || '[]')
    expect(stored.length).toBe(1)
    expect(stored[0].event_type).toBe('hall_enter')
    expect(stored[0].hall).toBe('relic-hall')
  })

  it('flushEvents sends buffered events to API', async () => {
    const { useTour } = await import('../useTour.js')
    const { createTourSession, bufferEvent, flushEvents, selectHall } = useTour()

    api.tour.createSession.mockResolvedValueOnce({
      ok: true,
      data: { id: 's1', session_token: 't1', status: 'onboarding' },
    })
    await createTourSession('A', 'A', 'A')

    api.tour.updateSession.mockResolvedValueOnce({ ok: true })
    api.exhibits.list.mockResolvedValueOnce({ ok: true, data: { exhibits: [] } })
    await selectHall('relic-hall')

    api.tour.recordEvents.mockResolvedValueOnce({ ok: true, data: { recorded: 1 } })

    bufferEvent('hall_enter', {})
    await flushEvents()

    expect(api.tour.recordEvents).toHaveBeenCalledWith(
      's1',
      expect.arrayContaining([expect.objectContaining({ event_type: 'hall_enter' })]),
      't1',
    )
  })

  it('completeHall transitions to hall-select when not all visited', async () => {
    const { useTour } = await import('../useTour.js')
    const { createTourSession, completeHall, tourStep } = useTour()

    api.tour.createSession.mockResolvedValueOnce({
      ok: true,
      data: { id: 's1', session_token: 't1', status: 'onboarding' },
    })
    await createTourSession('A', 'A', 'A')

    api.tour.completeHall.mockResolvedValueOnce({
      ok: true,
      data: { all_halls_visited: false },
    })

    await completeHall()

    expect(tourStep.value).toBe('hall-select')
  })

  it('completeHall transitions to report when all visited', async () => {
    const { useTour } = await import('../useTour.js')
    const { createTourSession, completeHall, tourStep } = useTour()

    api.tour.createSession.mockResolvedValueOnce({
      ok: true,
      data: { id: 's1', session_token: 't1', status: 'onboarding' },
    })
    await createTourSession('A', 'A', 'A')

    api.tour.completeHall.mockResolvedValueOnce({
      ok: true,
      data: { all_halls_visited: true },
    })

    await completeHall()

    expect(tourStep.value).toBe('report')
  })

  it('generateReport updates tourReport', async () => {
    const mockReport = {
      id: 'report-1',
      identity_tags: ['标签1', '标签2', '标签3'],
      radar_scores: { civilization_resonance: 2 },
      one_liner: '测试一句话',
    }

    const { useTour } = await import('../useTour.js')
    const { createTourSession, generateReport, tourReport } = useTour()

    api.tour.createSession.mockResolvedValueOnce({
      ok: true,
      data: { id: 's1', session_token: 't1', status: 'onboarding' },
    })
    await createTourSession('A', 'A', 'A')

    api.tour.generateReport.mockResolvedValueOnce({ ok: true, data: mockReport })

    await generateReport()

    expect(tourReport.value).toEqual(mockReport)
  })

  it('generateReport handles error', async () => {
    const { useTour } = await import('../useTour.js')
    const { createTourSession, generateReport, error } = useTour()

    api.tour.createSession.mockResolvedValueOnce({
      ok: true,
      data: { id: 's1', session_token: 't1', status: 'onboarding' },
    })
    await createTourSession('A', 'A', 'A')

    api.tour.generateReport.mockResolvedValueOnce({
      ok: false,
      data: { detail: 'Report generation failed' },
    })

    await generateReport()

    expect(error.value).toBe('Report generation failed')
  })

  it('resetTour clears all state', async () => {
    const { useTour } = await import('../useTour.js')
    const { createTourSession, resetTour, tourSession, tourStep, tourReport } = useTour()

    api.tour.createSession.mockResolvedValueOnce({
      ok: true,
      data: { id: 's1', session_token: 't1', status: 'onboarding' },
    })
    await createTourSession('A', 'A', 'A')

    resetTour()

    expect(tourSession.value).toBeNull()
    expect(tourStep.value).toBe('onboarding')
    expect(tourReport.value).toBeNull()
    expect(localStorage.getItem('tour_session_id')).toBeNull()
    expect(localStorage.getItem('tour_session_token')).toBeNull()
    expect(localStorage.getItem('tour_pending_events')).toBeNull()
  })

  it('personaLabel computes correct label', async () => {
    const { useTour } = await import('../useTour.js')
    const { createTourSession, personaLabel } = useTour()

    api.tour.createSession.mockResolvedValueOnce({
      ok: true,
      data: { id: 's1', session_token: 't1', persona: 'B', status: 'onboarding' },
    })
    await createTourSession('A', 'B', 'A')

    expect(personaLabel.value).toBe('半坡原住民')
  })

  it('reportThemeTitle computes correct title', async () => {
    const { useTour } = await import('../useTour.js')
    const { createTourSession, reportThemeTitle } = useTour()

    api.tour.createSession.mockResolvedValueOnce({
      ok: true,
      data: { id: 's1', session_token: 't1', persona: 'C', status: 'onboarding' },
    })
    await createTourSession('A', 'C', 'A')

    expect(reportThemeTitle.value).toBe('半坡游学荣誉证书')
  })
})
