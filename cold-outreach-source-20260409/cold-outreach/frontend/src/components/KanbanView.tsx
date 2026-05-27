import {
  DndContext,
  DragEndEvent,
  DragOverEvent,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCenter,
  DragOverlay,
} from '@dnd-kit/core'
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { useState } from 'react'
import { Lead, LeadStatus, LEAD_STATUS_LABELS, LEAD_STATUS_COLORS } from '@/types'
import { updateLeadStatus } from '@/lib/api'
import { useNavigate } from 'react-router-dom'

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return null
  const color = score >= 80 ? 'bg-green-100 text-green-700' : score >= 50 ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-500'
  return <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${color}`}>{score}</span>
}

function AvatarInitial({ name }: { name?: string | null }) {
  if (!name) return null
  const initials = name.split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase()
  const colors = ['bg-indigo-400', 'bg-purple-400', 'bg-pink-400', 'bg-blue-400', 'bg-teal-400']
  const color = colors[name.charCodeAt(0) % colors.length]
  return (
    <span className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-white text-xs font-medium ${color}`}>
      {initials}
    </span>
  )
}

interface KanbanCardProps {
  lead: Lead
  isDragging?: boolean
  onClick?: () => void
}

function KanbanCard({ lead, isDragging, onClick }: KanbanCardProps) {
  return (
    <div
      className={`bg-white border rounded-lg p-3 cursor-pointer hover:shadow-md transition-all select-none ${
        isDragging ? 'opacity-50 rotate-1 shadow-lg' : ''
      }`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-2">
        <p className="font-medium text-sm leading-tight">{lead.company_name}</p>
        <ScoreBadge score={lead.score} />
      </div>
      {lead.contact_name && (
        <p className="text-xs text-muted-foreground mb-1">
          {lead.contact_name}
          {lead.title && ` · ${lead.title}`}
        </p>
      )}
      {lead.industry && (
        <p className="text-xs text-gray-400">{lead.industry}</p>
      )}
      <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-50">
        <span className="text-xs text-muted-foreground">
          {new Date(lead.created_at).toLocaleDateString('zh-TW', { month: 'short', day: 'numeric' })}
        </span>
        <AvatarInitial name={lead.assigned_user?.name} />
      </div>
    </div>
  )
}

function SortableCard({ lead, onClick }: { lead: Lead; onClick: () => void }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: lead.id, data: { lead } })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <KanbanCard lead={lead} isDragging={isDragging} onClick={onClick} />
    </div>
  )
}

const COLUMN_COLORS: Record<LeadStatus, string> = {
  new: 'border-t-gray-400',
  contacted: 'border-t-blue-400',
  replied: 'border-t-yellow-400',
  meeting_scheduled: 'border-t-purple-400',
  mql: 'border-t-orange-400',
  sql: 'border-t-indigo-400',
  closed_won: 'border-t-emerald-500',
  closed_lost: 'border-t-rose-500',
  won: 'border-t-green-400',
  lost: 'border-t-red-400',
}

interface KanbanViewProps {
  leads: Lead[]
  onUpdate: () => void
}

export default function KanbanView({ leads, onUpdate }: KanbanViewProps) {
  const navigate = useNavigate()
  const [activeId, setActiveId] = useState<string | null>(null)
  const [localLeads, setLocalLeads] = useState<Lead[]>(leads)

  // Sync when parent updates
  if (leads !== localLeads && !activeId) {
    setLocalLeads(leads)
  }

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  )

  const columns = (Object.keys(LEAD_STATUS_LABELS) as LeadStatus[]).map(status => ({
    status,
    leads: localLeads.filter(l => l.status === status),
  }))

  const activeLead = activeId ? localLeads.find(l => l.id === activeId) : null

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string)
  }

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    setActiveId(null)

    if (!over) return

    const leadId = active.id as string
    const lead = localLeads.find(l => l.id === leadId)
    if (!lead) return

    // Determine target column
    let targetStatus: LeadStatus | null = null

    // Check if dropped on a column header/container
    const overId = over.id as string
    if (Object.keys(LEAD_STATUS_LABELS).includes(overId)) {
      targetStatus = overId as LeadStatus
    } else {
      // Dropped on another card — find its column
      const overLead = localLeads.find(l => l.id === overId)
      if (overLead) targetStatus = overLead.status
    }

    if (targetStatus && targetStatus !== lead.status) {
      // Optimistic update
      setLocalLeads(prev => prev.map(l =>
        l.id === leadId ? { ...l, status: targetStatus! } : l
      ))
      try {
        await updateLeadStatus(leadId, targetStatus)
        onUpdate()
      } catch {
        // Revert on error
        setLocalLeads(leads)
      }
    }
  }

  const handleDragOver = (event: DragOverEvent) => {
    const { active, over } = event
    if (!over) return

    const overId = over.id as string
    if (Object.keys(LEAD_STATUS_LABELS).includes(overId)) {
      const leadId = active.id as string
      setLocalLeads(prev => prev.map(l =>
        l.id === leadId ? { ...l, status: overId as LeadStatus } : l
      ))
    }
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-3 overflow-x-auto pb-4">
        {columns.map(col => (
          <div
            key={col.status}
            className="flex-shrink-0 w-64"
          >
            {/* Column header — also a drop target */}
            <div
              id={col.status}
              className={`bg-white border-2 border-t-4 rounded-xl ${COLUMN_COLORS[col.status]} p-3 mb-2`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold">{LEAD_STATUS_LABELS[col.status]}</span>
                <span className="text-xs text-muted-foreground bg-gray-100 px-1.5 py-0.5 rounded-full">
                  {col.leads.length}
                </span>
              </div>
            </div>

            {/* Cards */}
            <div
              id={col.status}
              className="space-y-2 min-h-16 rounded-lg p-1"
            >
              <SortableContext
                items={col.leads.map(l => l.id)}
                strategy={verticalListSortingStrategy}
              >
                {col.leads.map(lead => (
                  <SortableCard
                    key={lead.id}
                    lead={lead}
                    onClick={() => navigate(`/leads/${lead.id}`)}
                  />
                ))}
              </SortableContext>

              {col.leads.length === 0 && (
                <div className="h-16 border-2 border-dashed border-gray-100 rounded-lg flex items-center justify-center">
                  <span className="text-xs text-muted-foreground">拖曳至此</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <DragOverlay>
        {activeLead ? <KanbanCard lead={activeLead} isDragging /> : null}
      </DragOverlay>
    </DndContext>
  )
}
