import GmailEmailDetails from './GmailEmailDetails.jsx'

function toLegacyDetail(email) {
  const grouped = { people: [], organizations: [], dates: [], locations: [] }
  const keys = { person: 'people', organization: 'organizations', date: 'dates', location: 'locations' }
  email.entities.forEach((entity) => grouped[keys[entity.entity_type]]?.push(entity.entity_value))
  return {
    gmail: {
      sender: email.sender,
      recipients: email.recipients,
      subject: email.subject,
      received_at: email.received_at,
      labels: email.labels,
      body: email.body_original,
    },
    analysis: {
      sender: email.sender,
      subject: email.subject,
      summary: email.summary,
      classification: email.classification,
      reply_required: email.reply_required,
      tasks: email.tasks.map((task) => ({
        title: task.title,
        description: task.description,
        raw_deadline: task.raw_deadline,
        normalized_deadline: task.normalized_deadline,
      })),
      meeting: email.meeting ? {
        title: email.meeting.title,
        date: email.meeting.raw_date || email.meeting.normalized_date,
        time: email.meeting.time,
        participants: email.meeting.participants,
        location_or_link: email.meeting.location_or_link,
      } : null,
      entities: grouped,
    },
  }
}

export default function PersistedEmailDetails({ email, onClose }) {
  return <GmailEmailDetails item={toLegacyDetail(email)} onClose={onClose} />
}

