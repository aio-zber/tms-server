# GCG Team Messaging App

**A Viber-inspired team messaging application integrated with Team Management System (TMS)**

---

## 🛠️ Technology Stack

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - ORM for database management
- **Alembic** - Database migrations
- **Pydantic** - Data validation
- **python-socketio** - WebSocket server
- **PyJWT** - JWT token validation
- **PostgreSQL** - Primary database
- **Redis** - Caching & message queue

### Frontend
- **Next.js 14+** - React framework with App Router
- **TypeScript** - Type safety
- **TailwindCSS** - Utility-first CSS
- **shadcn/ui** - UI component library
- **Zustand** - Simple state management
- **Socket.io-client** - WebSocket client
- **React Hook Form** - Form handling
- **Zod** - Schema validation
- **date-fns** - Date manipulation

### Infrastructure
- **Railway** - Hosting platform
- **Cloudinary** - Media storage & optimization
- **GitHub Actions** - CI/CD pipeline

### Communication
- **WebSockets** - Real-time messaging
- **WebRTC** - Voice/video calls
- **HTTPS/TLS** - Encrypted communication

---
## 🎨 Viber UI/Design System

**Critical: This app should look and feel like Viber**

### Color Palette

#### Primary Colors
```css
--viber-purple: #7360F2          /* Main brand color */
--viber-purple-dark: #665DC1     /* Hover states */
--viber-purple-light: #9B8FFF    /* Active states */
--viber-purple-bg: #F5F3FF       /* Light backgrounds */
```

#### Neutral Colors
```css
--viber-gray-50: #F9FAFB         /* Backgrounds */
--viber-gray-100: #F3F4F6        /* Received message bubbles */
--viber-gray-200: #E5E7EB        /* Borders */
--viber-gray-400: #9CA3AF        /* Secondary text */
--viber-gray-600: #4B5563        /* Primary text */
--viber-gray-900: #111827        /* Headers */
```

#### Status Colors
```css
--viber-online: #10B981          /* Online status (green) */
--viber-away: #F59E0B            /* Away status (orange) */
--viber-offline: #6B7280         /* Offline (gray) */
--viber-error: #EF4444           /* Errors (red) */
--viber-success: #10B981         /* Success (green) */
```

#### Message Status
```css
--viber-sent: #9CA3AF            /* Single check (gray) */
--viber-delivered: #9CA3AF       /* Double check (gray) */
--viber-read: #7360F2            /* Double check (purple) */
```

### Typography
```css
--font-primary: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif
--font-size-xs: 11px             /* Timestamps */
--font-size-sm: 13px             /* Secondary text */
--font-size-base: 15px           /* Body text */
--font-size-lg: 17px             /* Headers */
--font-size-xl: 20px             /* Titles */
```

### Layout Structure

#### Desktop Layout (1024px+)
```
┌─────────────────────────────────────────────────┐
│  App Header (60px)                              │
│  [Logo] [Search] [Profile]                      │
├──────────────┬──────────────────────────────────┤
│              │                                   │
│  Sidebar     │  Chat Area                       │
│  (320px)     │  (Flexible width)                │
│              │                                   │
│  [Tabs]      │  [Chat Header]                   │
│  Chats       │  ┌──────────────────────────┐   │
│  Calls       │  │                          │   │
│  Contacts    │  │  Messages Area           │   │
│              │  │  (Scrollable)            │   │
│  [Chat List] │  │                          │   │
│  • Chat 1    │  └──────────────────────────┘   │
│  • Chat 2    │  [Message Input Composer]        │
│  • Chat 3    │                                   │
│              │                                   │
└──────────────┴──────────────────────────────────┘
```

#### Mobile Layout (<768px)
```
┌─────────────────────────┐
│  Top Bar (56px)         │
│  [Back] Title [Menu]    │
├─────────────────────────┤
│                         │
│  Content Area           │
│  (Full screen)          │
│                         │
│  [Stack Navigation]     │
│  Chat List → Chat View  │
│                         │
├─────────────────────────┤
│  Bottom Nav (56px)      │
│  [Chats][Calls][More]   │
└─────────────────────────┘
```

### Component Designs

#### Message Bubbles
**Sent Messages (Right-aligned)**
```
┌────────────────────────────────────────┐
│                    ┌──────────────┐    │
│                    │ Message text │    │
│                    │ content here │    │
│                    │  12:34 PM ✓✓ │    │
│                    └──────────────┘    │
└────────────────────────────────────────┘

Style:
- Background: #7360F2 (purple)
- Text: white
- Border-radius: 18px 18px 4px 18px
- Padding: 8px 12px
- Max-width: 75%
- Tail: small triangle bottom-right
- Status: checkmarks inline with time
```

**Received Messages (Left-aligned)**
```
┌────────────────────────────────────────┐
│  ┌──────────────┐                      │
│  │ Message text │                      │
│  │ content here │                      │
│  │ 12:34 PM     │                      │
│  └──────────────┘                      │
└────────────────────────────────────────┘

Style:
- Background: #F3F4F6 (light gray)
- Text: #111827 (dark)
- Border-radius: 18px 18px 18px 4px
- Padding: 8px 12px
- Max-width: 75%
- Tail: small triangle bottom-left
```

#### Chat List Item
```
┌────────────────────────────────────────────────┐
│  ┌──┐  John Doe                    12:34 PM    │
│  │ J│  Last message preview text...        [3] │
│  └──┘  ⚫                                       │
└────────────────────────────────────────────────┘

Layout:
- Avatar: 48px circle, left aligned
- Online dot: 10px green circle on avatar
- Name: Bold, 15px
- Time: Top-right, 13px, gray
- Message preview: 13px, gray, truncated
- Unread badge: Purple circle with white count
- Height: 72px
- Hover: slight gray background
```

#### Bottom Navigation (Mobile)
```
┌───────────────────────────────────────┐
│  [💬]     [📞]      [👤]      [⋯]   │
│  Chats    Calls    Contacts   More    │
└───────────────────────────────────────┘

Style:
- Height: 56px
- Background: white
- Border-top: 1px solid gray-200
- Icons: 24px
- Text: 11px
- Active: Purple color + bold
- Inactive: Gray color
```

#### Input Composer
```
┌────────────────────────────────────────────────┐
│  [📎] [😊]  Type a message...        [🎤/➤]   │
└────────────────────────────────────────────────┘

Components:
- Attachment button (paperclip): left
- Emoji button: next to attachment
- Input field: rounded, gray background, grows
- Mic button: right (when empty)
- Send button: right (purple, when typing)
- Height: 56px
- Border-radius: 24px on input
```

#### Floating Action Button (FAB)
```
Position: Bottom-right
Size: 56px circle
Color: Purple gradient
Icon: Pencil/compose (white)
Shadow: Elevated
Action: New conversation
```

### Animations & Transitions

#### Message Send Animation
```
1. Fade in from bottom
2. Scale from 0.9 to 1.0
3. Duration: 200ms
4. Easing: ease-out
```

#### Typing Indicator
```
Three dots bouncing animation
Color: Gray
Duration: 1.4s infinite
```

#### Scroll Behavior
```
- Smooth scroll: enabled
- Auto-scroll on new message: if near bottom
- Scroll-to-bottom button: appears when >200px from bottom
```

#### Hover States
```
- Chat items: slight gray background
- Buttons: darken 10%
- Message bubbles: show actions menu
- Transition: 150ms ease
```

### Icons & Illustrations

#### Icon Style
- **Style**: Outlined, 2px stroke
- **Size**: 20px (small), 24px (medium), 32px (large)
- **Color**: Gray-600 (default), Purple (active)

#### Key Icons
- Send: Arrow in circle
- Attach: Paperclip
- Emoji: Smiley face
- Voice: Microphone
- Video: Camera
- Call: Phone
- Search: Magnifying glass
- Menu: Three dots vertical
- Check: Single/double checkmarks

### Spacing System
```
--space-xs: 4px
--space-sm: 8px
--space-md: 12px
--space-lg: 16px
--space-xl: 24px
--space-2xl: 32px
```

### Border Radius
```
--radius-sm: 8px        /* Buttons */
--radius-md: 12px       /* Cards */
--radius-lg: 18px       /* Message bubbles */
--radius-full: 9999px   /* Avatars, badges */
```

### Shadows
```
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05)
--shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1)
--shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.1)
```

### Dark Mode Colors
```css
--viber-dark-bg: #0F0F0F
--viber-dark-surface: #1C1C1E
--viber-dark-border: #38383A
--viber-dark-text: #FFFFFF
--viber-dark-text-secondary: #98989D
--viber-sent-bubble-dark: #7360F2  /* Keep purple */
--viber-received-bubble-dark: #2C2C2E
```

---

## 📁 Project Structure & Organization

**Critical: Client and Server are SEPARATE repositories**

### Server Repository (FastAPI)

**Repository:** `chatflow-server/`

```
chatflow-server/                       # Server repository root
├── alembic/                           # Database migrations
│   ├── versions/                      # Migration files
│   └── env.py
│
├── app/
│   ├── main.py                        # FastAPI app entry (~100 lines)
│   ├── config.py                      # Configuration (~150 lines)
│   ├── dependencies.py                # Dependency injection (~200 lines)
│   │
│   ├── api/                          # API routes (thin controllers)
│   │   └── v1/                       # API version 1
│   │       ├── __init__.py
│   │       ├── auth.py               # Auth endpoints (~200 lines)
│   │       ├── messages.py           # Message endpoints (~300 lines)
│   │       ├── conversations.py      # Conversation endpoints (~250 lines)
│   │       ├── users.py              # User endpoints (~200 lines)
│   │       ├── calls.py              # Call endpoints (~250 lines)
│   │       ├── polls.py              # Poll endpoints (~150 lines)
│   │       ├── files.py              # File upload endpoints (~200 lines)
│   │       └── deps.py               # Route dependencies (~150 lines)
│   │
│   ├── core/                         # Core functionality
│   │   ├── __init__.py
│   │   ├── security.py               # Auth/JWT utils (~300 lines)
│   │   ├── tms_client.py             # TMS API client (~400 lines)
│   │   ├── cache.py                  # Redis operations (~250 lines)
│   │   ├── websocket.py              # WebSocket manager (~500 lines)
│   │   └── config.py                 # Configuration models (~200 lines)
│   │
│   ├── services/                     # Business logic (keep < 500 lines!)
│   │   ├── __init__.py
│   │   ├── message_service.py        # Message logic (~450 lines)
│   │   ├── conversation_service.py   # Conversation logic (~400 lines)
│   │   ├── user_service.py           # User sync logic (~350 lines)
│   │   ├── call_service.py           # Call logic (~400 lines)
│   │   ├── poll_service.py           # Poll logic (~300 lines)
│   │   ├── notification_service.py   # Notification logic (~350 lines)
│   │   └── file_service.py           # File handling (~350 lines)
│   │
│   ├── repositories/                 # Database access (one per table)
│   │   ├── __init__.py
│   │   ├── base.py                   # Base repository (~200 lines)
│   │   ├── message_repo.py           # Message CRUD (~300 lines)
│   │   ├── conversation_repo.py      # Conversation CRUD (~250 lines)
│   │   ├── user_repo.py              # User CRUD (~200 lines)
│   │   ├── call_repo.py              # Call CRUD (~200 lines)
│   │   └── poll_repo.py              # Poll CRUD (~200 lines)
│   │
│   ├── models/                       # SQLAlchemy models (one per table)
│   │   ├── __init__.py
│   │   ├── base.py                   # Base model (~50 lines)
│   │   ├── user.py                   # User model (~100 lines)
│   │   ├── conversation.py           # Conversation model (~120 lines)
│   │   ├── message.py                # Message model (~150 lines)
│   │   ├── call.py                   # Call model (~100 lines)
│   │   ├── poll.py                   # Poll model (~120 lines)
│   │   └── user_block.py             # User block model (~80 lines)
│   │
│   ├── schemas/                      # Pydantic schemas (request/response)
│   │   ├── __init__.py
│   │   ├── message.py                # Message schemas (~200 lines)
│   │   ├── conversation.py           # Conversation schemas (~150 lines)
│   │   ├── user.py                   # User schemas (~100 lines)
│   │   ├── call.py                   # Call schemas (~100 lines)
│   │   └── poll.py                   # Poll schemas (~120 lines)
│   │
│   ├── utils/                        # Utility functions
│   │   ├── __init__.py
│   │   ├── datetime.py               # Date utilities (~100 lines)
│   │   ├── validators.py             # Custom validators (~150 lines)
│   │   ├── formatters.py             # Data formatters (~100 lines)
│   │   └── helpers.py                # General helpers (~200 lines)
│   │
│   └── tests/                        # Tests mirror app structure
│       ├── __init__.py
│       ├── conftest.py               # Pytest fixtures (~300 lines)
│       ├── api/
│       │   └── v1/
│       │       ├── test_messages.py  (~400 lines)
│       │       └── test_conversations.py (~350 lines)
│       ├── services/
│       │   ├── test_message_service.py (~500 lines)
│       │   └── test_conversation_service.py (~450 lines)
│       └── repositories/
│           └── test_message_repo.py  (~400 lines)
│
├── .env.example                      # Environment template
├── .gitignore
├── requirements.txt                  # Python dependencies
├── pytest.ini                        # Pytest configuration
├── alembic.ini                       # Alembic configuration
├── Dockerfile                        # Docker config (optional)
└── README.md
```

### Client Repository (Next.js)

**Repository:** `chatflow-client/`

```
chatflow-client/                       # Client repository root
├── src/
│   ├── app/                          # Next.js 14 App Router
│   │   ├── layout.tsx                # Root layout (~150 lines)
│   │   ├── page.tsx                  # Landing page (~100 lines)
│   │   ├── globals.css               # Global styles
│   │   │
│   │   ├── (auth)/                   # Auth route group
│   │   │   ├── layout.tsx            # Auth layout (~100 lines)
│   │   │   └── login/
│   │   │       └── page.tsx          # Login page (~200 lines)
│   │   │
│   │   ├── (main)/                   # Main app route group
│   │   │   ├── layout.tsx            # Main layout (~250 lines)
│   │   │   ├── chats/
│   │   │   │   ├── page.tsx          # Chats list (~200 lines)
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx      # Chat view (~250 lines)
│   │   │   ├── calls/
│   │   │   │   └── page.tsx          # Calls page (~200 lines)
│   │   │   ├── contacts/
│   │   │   │   └── page.tsx          # Contacts page (~200 lines)
│   │   │   └── settings/
│   │   │       └── page.tsx          # Settings page (~300 lines)
│   │   │
│   │   └── api/                      # API routes (if needed)
│   │       └── webhooks/
│   │
│   ├── components/                   # React components (MAX 300 LINES!)
│   │   ├── chat/
│   │   │   ├── MessageBubble.tsx             (~150 lines)
│   │   │   ├── MessageList.tsx               (~250 lines)
│   │   │   ├── MessageInput.tsx              (~300 lines)
│   │   │   ├── ChatHeader.tsx                (~150 lines)
│   │   │   ├── ChatListItem.tsx              (~200 lines)
│   │   │   ├── ConversationList.tsx          (~250 lines)
│   │   │   ├── MessageReactions.tsx          (~150 lines)
│   │   │   ├── MessageActions.tsx            (~180 lines)
│   │   │   ├── TypingIndicator.tsx           (~80 lines)
│   │   │   └── VoiceMessagePlayer.tsx        (~200 lines)
│   │   │
│   │   ├── call/
│   │   │   ├── CallScreen.tsx                (~400 lines - complex OK)
│   │   │   ├── CallControls.tsx              (~200 lines)
│   │   │   ├── VideoGrid.tsx                 (~250 lines)
│   │   │   ├── IncomingCallModal.tsx         (~200 lines)
│   │   │   └── CallHistory.tsx               (~180 lines)
│   │   │
│   │   ├── poll/
│   │   │   ├── PollBubble.tsx                (~200 lines)
│   │   │   ├── PollCreator.tsx               (~250 lines)
│   │   │   └── PollResults.tsx               (~150 lines)
│   │   │
│   │   ├── ui/                       # shadcn/ui components
│   │   │   ├── button.tsx
│   │   │   ├── input.tsx
│   │   │   ├── avatar.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── dropdown-menu.tsx
│   │   │   └── toast.tsx
│   │   │
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx                   (~250 lines)
│   │   │   ├── TopBar.tsx                    (~180 lines)
│   │   │   ├── BottomNav.tsx                 (~150 lines)
│   │   │   └── FAB.tsx                       (~100 lines)
│   │   │
│   │   └── shared/                   # Shared components
│   │       ├── Avatar.tsx                    (~100 lines)
│   │       ├── EmojiPicker.tsx               (~250 lines)
│   │       ├── FileUpload.tsx                (~200 lines)
│   │       ├── VoiceRecorder.tsx             (~300 lines)
│   │       ├── ImageViewer.tsx               (~250 lines)
│   │       ├── SearchBar.tsx                 (~150 lines)
│   │       └── UserStatus.tsx                (~100 lines)
│   │
│   ├── features/                     # Feature modules (co-located)
│   │   ├── messaging/
│   │   │   ├── hooks/
│   │   │   │   ├── useMessages.ts            (~200 lines)
│   │   │   │   ├── useSendMessage.ts         (~150 lines)
│   │   │   │   ├── useMessageActions.ts      (~180 lines)
│   │   │   │   ├── useTyping.ts              (~100 lines)
│   │   │   │   └── useReactions.ts           (~120 lines)
│   │   │   ├── services/
│   │   │   │   └── messageService.ts         (~400 lines)
│   │   │   └── types.ts                      (~100 lines)
│   │   │
│   │   ├── conversations/
│   │   │   ├── hooks/
│   │   │   │   ├── useConversations.ts       (~200 lines)
│   │   │   │   ├── useConversation.ts        (~150 lines)
│   │   │   │   └── useConversationActions.ts (~180 lines)
│   │   │   ├── services/
│   │   │   │   └── conversationService.ts    (~350 lines)
│   │   │   └── types.ts                      (~80 lines)
│   │   │
│   │   ├── calls/
│   │   │   ├── hooks/
│   │   │   │   ├── useWebRTC.ts              (~500 lines - complex)
│   │   │   │   ├── useCallState.ts           (~250 lines)
│   │   │   │   └── useMediaDevices.ts        (~180 lines)
│   │   │   ├── services/
│   │   │   │   ├── callService.ts            (~400 lines)
│   │   │   │   └── signalingService.ts       (~300 lines)
│   │   │   └── types.ts                      (~100 lines)
│   │   │
│   │   ├── auth/
│   │   │   ├── hooks/
│   │   │   │   ├── useAuth.ts                (~200 lines)
│   │   │   │   └── useTMSSync.ts             (~150 lines)
│   │   │   ├── services/
│   │   │   │   └── authService.ts            (~250 lines)
│   │   │   └── types.ts                      (~60 lines)
│   │   │
│   │   └── files/
│   │       ├── hooks/
│   │       │   └── useFileUpload.ts          (~200 lines)
│   │       ├── services/
│   │       │   └── fileService.ts            (~300 lines)
│   │       └── types.ts                      (~50 lines)
│   │
│   ├── hooks/                        # Shared/global hooks
│   │   ├── useSocket.ts                      (~300 lines)
│   │   ├── useDebounce.ts                    (~50 lines)
│   │   ├── useIntersectionObserver.ts        (~80 lines)
│   │   ├── useMediaQuery.ts                  (~60 lines)
│   │   ├── useOnlineStatus.ts                (~100 lines)
│   │   └── useLocalStorage.ts                (~120 lines)
│   │
│   ├── lib/                          # Libraries/utilities
│   │   ├── socket.ts                         # Socket.io setup (~250 lines)
│   │   ├── api.ts                            # API client (~300 lines)
│   │   ├── utils.ts                          # General utilities (~300 lines)
│   │   ├── cn.ts                             # classNames utility (~30 lines)
│   │   └── constants.ts                      # App constants (~150 lines)
│   │
│   ├── store/                        # Zustand stores (one per domain)
│   │   ├── authStore.ts                      (~150 lines)
│   │   ├── conversationStore.ts              (~300 lines)
│   │   ├── messageStore.ts                   (~350 lines)
│   │   ├── callStore.ts                      (~250 lines)
│   │   ├── userStore.ts                      (~200 lines)
│   │   ├── notificationStore.ts              (~180 lines)
│   │   └── settingsStore.ts                  (~150 lines)
│   │
│   ├── styles/
│   │   ├── globals.css                       # Global styles
│   │   └── viber-theme.css                   # Viber CSS variables
│   │
│   ├── types/                        # TypeScript types (global)
│   │   ├── index.ts                          (~50 lines)
│   │   ├── message.ts                        (~120 lines)
│   │   ├── conversation.ts                   (~100 lines)
│   │   ├── user.ts                           (~80 lines)
│   │   ├── call.ts                           (~100 lines)
│   │   └── api.ts                            (~150 lines)
│   │
│   └── utils/                        # Utility functions
│       ├── date.ts                           (~150 lines)
│       ├── format.ts                         (~200 lines)
│       ├── validation.ts                     (~250 lines)
│       └── encryption.ts                     (~200 lines - Phase 3)
│
├── public/
│   ├── icons/                        # Icon assets
│   ├── sounds/                       # Notification sounds
│   ├── images/                       # Static images
│   └── sw.js                         # Service worker (PWA)
│
├── __tests__/                        # Test files mirror src structure
│   ├── components/
│   ├── hooks/
│   └── services/
│
├── .env.local.example
├── .eslintrc.json
├── .prettierrc
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
├── jest.config.js
├── package.json
├── Dockerfile                        # Docker config (optional)
└── README.md
```

---

## 🔗 Client-Server Communication

**Critical: Client and Server are separate services that communicate via HTTP/WebSocket**

### Development Environment

```
Server:     http://localhost:8000
Client:     http://localhost:3000
WebSocket:  ws://localhost:8000/ws
API:        http://localhost:8000/api/v1
```

### Environment Variables

#### Server (.env)
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/chatflow
REDIS_URL=redis://localhost:6379

# TMS Integration
TMS_API_URL=https://tms.example.com
TMS_API_KEY=your-tms-api-key-here

# Security
JWT_SECRET=your-super-secret-jwt-key-min-32-chars
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com

# File Upload
CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name
MAX_UPLOAD_SIZE=10485760  # 10MB in bytes

# Environment
ENVIRONMENT=development
DEBUG=true
```

#### Client (.env.local)
```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# Cloudinary (for direct uploads if needed)
NEXT_PUBLIC_CLOUDINARY_CLOUD_NAME=your-cloud-name
NEXT_PUBLIC_CLOUDINARY_UPLOAD_PRESET=your-upload-preset

# Environment
NEXT_PUBLIC_ENVIRONMENT=development
```

### CORS Configuration

**Server must allow client origin:**

```python
# server/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",      # Development
        "https://yourdomain.com",     # Production client
        "https://app.yourdomain.com"  # Production client (alternative)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### API Client Setup

**Client API configuration:**

```typescript
// client/src/lib/api.ts
import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor (add auth token)
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor (handle errors)
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Redirect to login
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
```

### Deployment Strategy

#### Separate Deployments

**Server (Railway):**
- Deploy FastAPI app to Railway
- PostgreSQL database on Railway
- Redis on Railway
- Environment variables configured in Railway dashboard
- URL: `https://api.yourdomain.com`

**Client (Railway or Vercel):**
- Deploy Next.js app to Railway or Vercel
- Environment variables configured in platform dashboard
- Update `NEXT_PUBLIC_API_URL` to production server URL
- URL: `https://yourdomain.com` or `https://app.yourdomain.com`

#### Production Environment Variables

**Server:**
```bash
DATABASE_URL=<railway-postgres-url>
REDIS_URL=<railway-redis-url>
ALLOWED_ORIGINS=https://yourdomain.com
ENVIRONMENT=production
DEBUG=false
```

**Client:**
```bash
NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api/v1
NEXT_PUBLIC_WS_URL=wss://api.yourdomain.com
NEXT_PUBLIC_ENVIRONMENT=production
```

---

## 🛠️ Development Workflow

### Initial Setup

#### Server Setup

```bash
# Clone server repository
git clone <server-repo-url>
cd chatflow-server

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Unix/MacOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your configuration
# nano .env or code .env

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --port 8000
```

Server will be running at `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

#### Client Setup

```bash
# Clone client repository
git clone <client-repo-url>
cd chatflow-client

# Install dependencies
npm install
# or: yarn install / pnpm install

# Copy environment template
cp .env.local.example .env.local

# Edit .env.local with your configuration
# nano .env.local or code .env.local

# Start development server
npm run dev
```

Client will be running at `http://localhost:3000`

### Running Both Services

#### Option 1: Separate Terminal Windows/Tabs

**Terminal 1 (Server):**
```bash
cd chatflow-server
source venv/bin/activate  # or venv\Scripts\activate on Windows
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 (Client):**
```bash
cd chatflow-client
npm run dev
```

#### Option 2: Docker Compose (Recommended)

Create `docker-compose.yml` in a parent directory:

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: chatflow
      POSTGRES_USER: chatflow
      POSTGRES_PASSWORD: chatflow_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U chatflow"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis Cache
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # FastAPI Server
  server:
    build:
      context: ./chatflow-server
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://chatflow:chatflow_password@db:5432/chatflow
      REDIS_URL: redis://redis:6379
      TMS_API_URL: ${TMS_API_URL}
      TMS_API_KEY: ${TMS_API_KEY}
      JWT_SECRET: ${JWT_SECRET}
      ALLOWED_ORIGINS: http://localhost:3000
      ENVIRONMENT: development
      DEBUG: "true"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./chatflow-server:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  # Next.js Client
  client:
    build:
      context: ./chatflow-client
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000/api/v1
      NEXT_PUBLIC_WS_URL: ws://localhost:8000
      NEXT_PUBLIC_ENVIRONMENT: development
    depends_on:
      - server
    volumes:
      - ./chatflow-client:/app
      - /app/node_modules
      - /app/.next
    command: npm run dev

volumes:
  postgres_data:
  redis_data:
```

**Usage:**
```bash
# Start all services
docker-compose up

# Start in background
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f

# Rebuild after changes
docker-compose up --build
```

### Common Development Tasks

#### Database Migrations

```bash
cd chatflow-server

# Create new migration
alembic revision --autogenerate -m "Add user table"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

#### Testing

**Server:**
```bash
cd chatflow-server
pytest                           # Run all tests
pytest tests/services/          # Run specific directory
pytest -v                        # Verbose output
pytest --cov=app                 # With coverage
```

**Client:**
```bash
cd chatflow-client
npm run test                     # Run all tests
npm run test:watch              # Watch mode
npm run test:coverage           # With coverage
npm run test MessageBubble      # Run specific test
```

#### Code Quality

**Server:**
```bash
# Format code
black app/
isort app/

# Lint
flake8 app/
mypy app/

# All checks
black app/ && isort app/ && flake8 app/ && mypy app/
```

**Client:**
```bash
# Format code
npm run format

# Lint
npm run lint

# Type check
npm run type-check

# All checks
npm run lint && npm run type-check
```

### Troubleshooting

**Server won't start:**
- Check database connection (`DATABASE_URL` correct?)
- Check Redis connection (`REDIS_URL` correct?)
- Verify virtual environment is activated
- Check port 8000 is not in use: `lsof -i :8000` (Mac/Linux)

**Client won't start:**
- Check Node version (need 18+): `node --version`
- Delete `node_modules` and reinstall: `rm -rf node_modules && npm install`
- Clear Next.js cache: `rm -rf .next`
- Check port 3000 is not in use

**CORS errors:**
- Verify `ALLOWED_ORIGINS` in server .env includes client URL
- Check client is using correct API URL
- Restart server after changing CORS config

**WebSocket connection fails:**
- Check `NEXT_PUBLIC_WS_URL` is correct
- Verify server WebSocket endpoint is running
- Check firewall/proxy settings

---

## 📏 File Organization Best Practices

### File Size Quick Reference

| File Type | Target Lines | Maximum Lines | Notes |
|-----------|--------------|---------------|-------|
| React Components | 150-250 | 300 | Split if larger |
| Custom Hooks | 100-150 | 200 | Extract logic |
| Service Files | 300-400 | 500 | Use composition |
| API Routes | 200-250 | 300 | Keep thin |
| Store/State | 150-200 | 250 | Split by domain |
| Utility Files | 150-250 | 300 | Group related |
| Type Definitions | 80-120 | 150 | Split by domain |
| Models (SQLAlchemy) | 80-120 | 150 | One per table |
| **Complex Features** | 400-500 | **600** | WebRTC, Calls only |
| Test Files | 300-500 | 800 | Many test cases OK |

**If file exceeds maximum:** Refactor immediately using:
- Single Responsibility Principle (one file, one responsibility)
- Extract logic to hooks or utilities
- Create sub-components
- Use service composition

### How to Keep Files Small

#### 1. **Single Responsibility Principle** (SRP)
```typescript
// ❌ BAD: One file doing everything (800+ lines)
// MessageComponent.tsx - rendering, logic, API calls, state

// ✅ GOOD: Split by responsibility
// MessageBubble.tsx          (~150 lines - display only)
// MessageInput.tsx           (~200 lines - input handling)
// MessageActions.tsx         (~150 lines - action menu)
// useMessageOperations.ts    (~200 lines - business logic)
// messageService.ts          (~300 lines - API calls)
// messageStore.ts            (~200 lines - state management)
```

#### 2. **Extract Custom Hooks**
```typescript
// ❌ BAD: All logic in component (500+ lines)
function ChatScreen() {
  const [messages, setMessages] = useState([]);
  const [isTyping, setIsTyping] = useState(false);

  useEffect(() => {
    // 50 lines of socket logic
  }, []);

  const sendMessage = async () => {
    // 30 lines of send logic
  };

  // ... many more handlers
}

// ✅ GOOD: Extract to hooks (component: ~150 lines)
function ChatScreen() {
  const { messages, loading } = useMessages(conversationId);
  const { sendMessage, sending } = useSendMessage();
  const { isTyping } = useTyping(conversationId);
  const { connect, disconnect } = useSocket();

  // Clean and focused component logic
}

// hooks/useMessages.ts (~200 lines)
// hooks/useSendMessage.ts (~150 lines)
// hooks/useTyping.ts (~100 lines)
// hooks/useSocket.ts (~250 lines)
```

#### 3. **Create Sub-Components**
```typescript
// ❌ BAD: Monolithic component with nested JSX (400+ lines)
function MessageBubble({ message }) {
  return (
    <div className="message-bubble">
      {/* 20 lines for header */}
      <div className="header">...</div>

      {/* 30 lines for body */}
      <div className="body">...</div>

      {/* 25 lines for media */}
      <div className="media">...</div>

      {/* 20 lines for reactions */}
      <div className="reactions">...</div>

      {/* 15 lines for footer */}
      <div className="footer">...</div>
    </div>
  );
}

// ✅ GOOD: Composition with sub-components (~80 lines)
function MessageBubble({ message }) {
  return (
    <div className="message-bubble">
      <MessageHeader message={message} />
      <MessageBody content={message.content} />
      <MessageMedia media={message.media} />
      <MessageReactions reactions={message.reactions} />
      <MessageFooter message={message} />
    </div>
  );
}

// MessageHeader.tsx (~100 lines)
// MessageBody.tsx (~120 lines)
// MessageMedia.tsx (~150 lines)
// MessageReactions.tsx (~140 lines)
// MessageFooter.tsx (~100 lines)
```

#### 4. **Service Composition**
```typescript
// ❌ BAD: Monolithic service (1000+ lines)
class MessageService {
  async send() { /* 50 lines */ }
  async edit() { /* 40 lines */ }
  async delete() { /* 35 lines */ }
  async react() { /* 30 lines */ }
  async forward() { /* 45 lines */ }
  async reply() { /* 40 lines */ }
  async pin() { /* 35 lines */ }
  async search() { /* 60 lines */ }
  // ... 15 more methods
}

// ✅ GOOD: Compose smaller, focused services
class MessageService {
  constructor(
    private sender: MessageSender,       // ~150 lines
    private editor: MessageEditor,       // ~150 lines
    private deleter: MessageDeleter,     // ~100 lines
    private reactor: MessageReactor,     // ~100 lines
    private forwarder: MessageForwarder, // ~120 lines
  ) {}

  // Delegates to specialized services
  async send(data) { return this.sender.send(data); }
  async edit(id, data) { return this.editor.edit(id, data); }
  // ... slim delegators
}
```

#### 5. **Type File Organization**
```typescript
// ❌ BAD: All types in one file (500+ lines)
// types/index.ts - everything

// ✅ GOOD: Split by domain
// types/message.ts      (~120 lines)
// types/conversation.ts (~100 lines)
// types/user.ts         (~80 lines)
// types/call.ts         (~100 lines)
// types/api.ts          (~150 lines)
```

---

## 🎯 Module Organization Principles

### 1. **Feature-Based Structure** (Recommended)

**Group by feature, not by file type**

```
✅ GOOD - Feature-based:
features/
├── messaging/
│   ├── components/
│   ├── hooks/
│   ├── services/
│   ├── types.ts
│   └── index.ts
├── calls/
│   ├── components/
│   ├── hooks/
│   └── services/
└── auth/
    └── ...

❌ AVOID - Type-based (harder to maintain):
components/
├── MessageBubble.tsx
├── MessageList.tsx
├── CallScreen.tsx
├── CallControls.tsx
└── ... (100+ files mixed together)
```

### 2. **Separation of Concerns (Layered Architecture)**

```
Presentation Layer → Domain Layer → Data Layer
     (UI)          → (Business Logic) → (API/DB)

Backend:
API Routes → Services → Repositories → Models
(thin)      (fat)      (thin)         (data)

Frontend:
Components → Hooks → Services → API Client
(presentation) (logic) (business) (data)
```

**Example:**
```typescript
// ✅ GOOD: Clear layer separation

// 1. Component (Presentation) - ~150 lines
function MessageList() {
  const { messages } = useMessages(); // Hook
  return messages.map(msg => <MessageBubble key={msg.id} {...msg} />);
}

// 2. Hook (Domain Logic) - ~200 lines
function useMessages() {
  const [messages, setMessages] = useState([]);

  useEffect(() => {
    messageService.getMessages().then(setMessages);
  }, []);

  return { messages };
}

// 3. Service (Business Logic) - ~300 lines
class MessageService {
  async getMessages() {
    const response = await apiClient.get('/messages');
    return this.transform(response.data);
  }

  private transform(data) { /* business logic */ }
}

// 4. API Client (Data) - ~250 lines
const apiClient = {
  async get(url) {
    return axios.get(url, { headers: authHeaders });
  }
};
```

### 3. **Dependency Direction**

**Always depend inward (toward domain):**

```
✅ CORRECT dependency flow:
Outer Layer → Inner Layer

Components → Hooks → Services → Models
UI         → Logic → Business → Data

❌ WRONG: Inner layers should NOT depend on outer layers
Services should NOT import Components
Models should NOT import Services
```

### 4. **Co-location**

**Keep related code together:**

```
✅ GOOD: Co-located by feature
features/messaging/
├── MessageBubble.tsx       # Component
├── useMessages.ts          # Hook for component
├── messageService.ts       # Service used by hook
└── types.ts                # Types used by all above

❌ AVOID: Scattered across folders
components/MessageBubble.tsx
hooks/useMessages.ts
services/messageService.ts
types/message.ts
```

---

## 🏷️ Naming Conventions

### File Naming

```
Components:          PascalCase      MessageBubble.tsx
Hooks:               camelCase       useMessages.ts
Services:            camelCase       messageService.ts
Utilities:           camelCase       formatDate.ts
Types:               camelCase       message.ts (exports PascalCase types)
Constants:           camelCase       apiEndpoints.ts
Tests:               match source    MessageBubble.test.tsx
```

### Code Naming

```typescript
// Components: PascalCase
export function MessageBubble() { }
export const ChatScreen = () => { };

// Hooks: camelCase with 'use' prefix
export function useMessages() { }
export const useSendMessage = () => { };

// Services: PascalCase class or camelCase object
export class MessageService { }
export const messageService = { };

// Types/Interfaces: PascalCase
export interface Message { }
export type ConversationType = 'dm' | 'group';

// Constants: UPPER_SNAKE_CASE
export const MAX_MESSAGE_LENGTH = 10000;
export const API_BASE_URL = process.env.API_URL;

// Functions: camelCase
export function formatDate(date: Date) { }
export const calculateDuration = () => { };

// Variables: camelCase
const messageList = [];
let isTyping = false;
```

### Folder Naming

```
Lowercase with dashes:   message-actions/
Lowercase:               components/
PascalCase (routes):     app/(main)/Chats/
```

---

## 🧩 Component Design Guidelines

### Component Size & Complexity

```typescript
// ✅ IDEAL: Small, focused components (100-200 lines)
function MessageBubble({ message }) {
  const { handleReact, handleReply } = useMessageActions();

  return (
    <div className="message-bubble">
      <MessageContent content={message.content} />
      <MessageFooter timestamp={message.createdAt} />
    </div>
  );
}

// Target metrics:
// - Lines: 100-300
// - Props: max 10
// - Hooks: max 5-7
// - Nesting: max 4 levels
// - Functions: max 5-7
```

### Extract Logic to Hooks

```typescript
// ❌ BAD: Logic in component
function ChatScreen() {
  const [messages, setMessages] = useState([]);

  useEffect(() => {
    socket.on('message', (msg) => {
      setMessages(prev => [...prev, msg]);
    });
  }, []);

  const sendMessage = async (content) => {
    const response = await fetch('/api/messages', {
      method: 'POST',
      body: JSON.stringify({ content })
    });
    // ... 20 more lines
  };

  // ... more logic
}

// ✅ GOOD: Logic in hooks
function ChatScreen() {
  const { messages } = useMessages(conversationId);
  const { sendMessage } = useSendMessage(conversationId);
  const socket = useSocket();

  return <MessageList messages={messages} onSend={sendMessage} />;
}
```

### Props Guidelines

```typescript
// ✅ GOOD: Few, well-defined props
interface MessageBubbleProps {
  message: Message;
  onReply?: (id: string) => void;
  onReact?: (id: string, emoji: string) => void;
}

// ❌ AVOID: Too many props (hard to maintain)
interface MessageBubbleProps {
  id: string;
  content: string;
  sender: User;
  timestamp: Date;
  isEdited: boolean;
  reactions: Reaction[];
  replies: Message[];
  status: Status;
  onReply: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onReact: () => void;
  // ... 10 more props
}

// ✅ BETTER: Group related props
interface MessageBubbleProps {
  message: Message;      // Contains id, content, sender, etc.
  actions: {             // Group action handlers
    onReply: () => void;
    onEdit: () => void;
    onDelete: () => void;
  };
}
```

### Use Composition

```typescript
// ✅ GOOD: Composition pattern
function ChatScreen() {
  return (
    <div>
      <ChatHeader />
      <MessageList />
      <MessageInput />
    </div>
  );
}

// Better than conditional rendering hell:
// ❌ AVOID
function ChatScreen() {
  return (
    <div>
      {isLoading ? <Spinner /> : null}
      {error ? <Error /> : null}
      {messages.length === 0 ? <EmptyState /> : (
        messages.map(msg => (
          msg.type === 'text' ? <TextMessage /> :
          msg.type === 'image' ? <ImageMessage /> :
          msg.type === 'file' ? <FileMessage /> :
          msg.type === 'voice' ? <VoiceMessage /> : null
        ))
      )}
    </div>
  );
}
```

---

## 📦 Import Organization

### Standard Import Order

```typescript
// 1. React/Next.js imports
import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

// 2. External library imports
import { io } from 'socket.io-client';
import { format } from 'date-fns';
import { z } from 'zod';

// 3. Internal component imports
import { MessageBubble } from '@/components/chat/MessageBubble';
import { ChatHeader } from '@/components/chat/ChatHeader';

// 4. Internal hook imports
import { useMessages } from '@/features/messaging/hooks/useMessages';
import { useSocket } from '@/hooks/useSocket';

// 5. Internal service/util imports
import { messageService } from '@/features/messaging/services/messageService';
import { formatDate } from '@/utils/date';

// 6. Type imports
import type { Message, Conversation } from '@/types';

// 7. Style imports
import styles from './ChatScreen.module.css';
```

### Path Aliases (tsconfig.json)

```json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"],
      "@/components/*": ["./src/components/*"],
      "@/features/*": ["./src/features/*"],
      "@/hooks/*": ["./src/hooks/*"],
      "@/lib/*": ["./src/lib/*"],
      "@/utils/*": ["./src/utils/*"],
      "@/types/*": ["./src/types/*"]
    }
  }
}
```

---

## 🧪 Testing Structure

### Mirror App Structure

```
Frontend:
src/
├── components/chat/MessageBubble.tsx
└── hooks/useMessages.ts

__tests__/
├── components/chat/MessageBubble.test.tsx
└── hooks/useMessages.test.ts

Backend:
app/
├── services/message_service.py
└── api/v1/messages.py

tests/
├── services/test_message_service.py
└── api/v1/test_messages.py
```

### Test File Guidelines

```typescript
// Test file naming: SourceFile.test.ts(x)
// MessageBubble.tsx → MessageBubble.test.tsx

// ✅ GOOD: Organized test structure (~400 lines)
describe('MessageBubble', () => {
  describe('Rendering', () => {
    it('renders text messages correctly', () => { });
    it('renders image messages correctly', () => { });
    // ... 5-10 render tests
  });

  describe('Interactions', () => {
    it('handles reply click', () => { });
    it('handles reaction click', () => { });
    // ... 5-10 interaction tests
  });

  describe('Edge Cases', () => {
    it('handles deleted messages', () => { });
    it('handles edited messages', () => { });
    // ... 5-10 edge case tests
  });
});

// Test file size guidelines:
// - Unit tests: 300-600 lines
// - Integration tests: 400-800 lines
// - E2E tests: 200-400 lines per spec
```

### Testing Best Practices

```typescript
// 1. One assertion per test (mostly)
✅ it('renders message content', () => {
  render(<MessageBubble message={mockMessage} />);
  expect(screen.getByText('Hello')).toBeInTheDocument();
});

// 2. Clear test descriptions
✅ it('shows edited indicator when message is edited', () => { });
❌ it('works', () => { });

// 3. Use factories/fixtures for test data
✅ const mockMessage = createMockMessage({ content: 'Hello' });
❌ const mockMessage = { id: '1', content: 'Hello', /* 20 more fields */ };

// 4. Group related tests
✅ describe('MessageBubble', () => {
  describe('when message is sent by current user', () => { });
  describe('when message is sent by other user', () => { });
});
```

---

## ✅ Quick Best Practices Summary

**Essential Rules for Clean Code:**

### File Organization
- ✅ Keep files under maximum lines (see table above)
- ✅ One responsibility per file
- ✅ Name files correctly (Components: PascalCase, hooks: camelCase with 'use')
- ✅ Co-locate related code (feature-based structure)
- ✅ Follow standard import order

### Code Quality
- ✅ No `any` types in TypeScript (use proper types)
- ✅ Extract logic to hooks (components should be simple)
- ✅ DRY principle (don't repeat yourself)
- ✅ Proper error handling (try-catch, error boundaries)
- ✅ Clear naming (functions do what their name says)

### Component Design
- ✅ Max 10 props per component (group related props)
- ✅ Max 5-7 hooks per component
- ✅ Extract sub-components when JSX gets nested
- ✅ Use composition over conditional rendering hell

### Architecture
- ✅ Components → Hooks → Services → API (clear layers)
- ✅ Never import outer layers from inner layers
- ✅ Keep API routes thin (delegate to services)
- ✅ Services handle business logic (no UI code)

### Testing
- ✅ Mirror app structure in tests
- ✅ One test file per source file
- ✅ Clear test descriptions
- ✅ Target: 70% frontend, 80% backend coverage

### Git/PR
- ✅ Commit often with clear messages
- ✅ Keep PRs small (<500 lines changed ideal)
- ✅ Review checklist before submitting
- ✅ Ensure all tests pass

**Remember:** If a file is too large or complex, split it immediately!

---

## 📋 Code Review Checklist

**Before submitting PR, verify:**

**File Organization:**
- [ ] No file exceeds size limits (components: 300, services: 500)
- [ ] Files follow naming conventions
- [ ] Related code is co-located
- [ ] Imports are organized correctly

**Code Quality:**
- [ ] Single Responsibility Principle followed
- [ ] No code duplication (DRY)
- [ ] Clear separation of concerns
- [ ] Proper error handling
- [ ] Type safety (no `any` types)

**Components:**
- [ ] Max 10 props per component
- [ ] Logic extracted to hooks
- [ ] Composition over complexity
- [ ] Proper TypeScript types

**Testing:**
- [ ] Unit tests for business logic
- [ ] Component tests for UI
- [ ] Tests mirror source structure
- [ ] Good test coverage (70%+ frontend, 80%+ backend)

**Documentation:**
- [ ] Complex functions have comments
- [ ] README updated if needed
- [ ] API changes documented

---


## 🔐 TMS Integration
**Critical: TMA relies on Team Management System (TMS) for user identity and authentication**

### Authentication & SSO
- **SSO/Token Validation** - Validate TMS JWT/session tokens on every request
- **Session Management** - Handle TMS session validation and expiry
- **Token Refresh** - Refresh expired TMS tokens automatically
- **Cross-Origin Authentication** - Handle authentication across TMS and TMA domains (CORS)
- **Logout Handling** - Sync logout with TMS

### User Data Integration
- **TMS API Integration** - Fetch user data from TMS (username, email, position, avatar, role)
- **User Data Caching** - Cache TMS user data in Redis (TTL: 5-15 minutes)
- **User Sync Service** - Periodic background sync of user data (every 10 minutes)
- **Real-time Updates** - TMS webhooks for instant user data updates (preferred)
- **Batch User Fetch** - Fetch multiple users efficiently (single API call)
- **User Profile Display** - Display TMS user data (view-only, managed by TMS)

### Authorization & Permissions
- **Role Mapping** - Map TMS roles to TMA permissions (admin, user, etc.)
- **Permission Validation** - Validate user permissions for actions
- **Group Admin Rights** - Determine admin rights based on TMS roles
- **Access Control** - Control feature access based on TMS permissions

### TMS Communication
- **TMS API Client** - Secure HTTP client for TMS communication
- **API Key Management** - Secure storage of TMS API credentials (environment variables)
- **Rate Limit Handling** - Handle TMS API rate limits gracefully
- **Error Handling** - Graceful handling of TMS API failures (fallback to cache)
- **Health Checks** - Monitor TMS API availability (ping endpoint)

---

## 🏗️ Core Infrastructure

### Database Architecture

#### Core Tables Schema
```sql
-- User reference (TMS sync)
users (
  id UUID PRIMARY KEY,
  tms_user_id VARCHAR UNIQUE NOT NULL,
  settings_json JSONB DEFAULT '{}',
  last_synced_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
)

-- Conversations
conversations (
  id UUID PRIMARY KEY,
  type VARCHAR NOT NULL CHECK(type IN ('dm', 'group')),
  name VARCHAR,
  avatar_url VARCHAR,
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
)

-- Conversation members
conversation_members (
  conversation_id UUID REFERENCES conversations(id),
  user_id UUID REFERENCES users(id),
  role VARCHAR DEFAULT 'member' CHECK(role IN ('admin', 'member')),
  joined_at TIMESTAMP DEFAULT NOW(),
  last_read_at TIMESTAMP,
  is_muted BOOLEAN DEFAULT FALSE,
  mute_until TIMESTAMP,
  PRIMARY KEY (conversation_id, user_id)
)

-- Messages
messages (
  id UUID PRIMARY KEY,
  conversation_id UUID REFERENCES conversations(id),
  sender_id UUID REFERENCES users(id),
  content TEXT,
  type VARCHAR NOT NULL CHECK(type IN ('text', 'image', 'file', 'voice', 'poll', 'call')),
  metadata_json JSONB DEFAULT '{}',
  reply_to_id UUID REFERENCES messages(id),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP,
  deleted_at TIMESTAMP,
  is_edited BOOLEAN DEFAULT FALSE
)

-- Message status (delivery/read receipts)
message_status (
  message_id UUID REFERENCES messages(id),
  user_id UUID REFERENCES users(id),
  status VARCHAR NOT NULL CHECK(status IN ('sent', 'delivered', 'read')),
  timestamp TIMESTAMP DEFAULT NOW(),
  PRIMARY KEY (message_id, user_id)
)

-- Message reactions
message_reactions (
  id UUID PRIMARY KEY,
  message_id UUID REFERENCES messages(id),
  user_id UUID REFERENCES users(id),
  emoji VARCHAR NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(message_id, user_id, emoji)
)

-- User blocks
user_blocks (
  blocker_id UUID REFERENCES users(id),
  blocked_id UUID REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW(),
  PRIMARY KEY (blocker_id, blocked_id)
)

-- Calls
calls (
  id UUID PRIMARY KEY,
  conversation_id UUID REFERENCES conversations(id),
  type VARCHAR NOT NULL CHECK(type IN ('voice', 'video')),
  status VARCHAR NOT NULL CHECK(status IN ('completed', 'missed', 'declined', 'cancelled')),
  started_at TIMESTAMP,
  ended_at TIMESTAMP,
  created_by UUID REFERENCES users(id)
)

-- Call participants
call_participants (
  call_id UUID REFERENCES calls(id),
  user_id UUID REFERENCES users(id),
  joined_at TIMESTAMP,
  left_at TIMESTAMP,
  PRIMARY KEY (call_id, user_id)
)

-- Polls
polls (
  id UUID PRIMARY KEY,
  message_id UUID REFERENCES messages(id) UNIQUE,
  question TEXT NOT NULL,
  multiple_choice BOOLEAN DEFAULT FALSE,
  expires_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
)

-- Poll options
poll_options (
  id UUID PRIMARY KEY,
  poll_id UUID REFERENCES polls(id),
  option_text VARCHAR NOT NULL,
  position INT NOT NULL
)

-- Poll votes
poll_votes (
  id UUID PRIMARY KEY,
  poll_id UUID REFERENCES polls(id),
  option_id UUID REFERENCES poll_options(id),
  user_id UUID REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(poll_id, option_id, user_id)
)

-- Encryption keys (for E2EE - Phase 3)
encryption_keys (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  device_id VARCHAR NOT NULL,
  public_key TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, device_id)
)
```

#### Database Indexes
```sql
CREATE INDEX idx_messages_conversation_created ON messages(conversation_id, created_at DESC);
CREATE INDEX idx_messages_sender ON messages(sender_id);
CREATE INDEX idx_conversation_members_user ON conversation_members(user_id);
CREATE INDEX idx_message_status_user ON message_status(user_id, status);
CREATE INDEX idx_user_blocks_blocker ON user_blocks(blocker_id);
CREATE INDEX idx_user_blocks_blocked ON user_blocks(blocked_id);
CREATE INDEX idx_users_tms_user_id ON users(tms_user_id);
CREATE INDEX idx_messages_reply_to ON messages(reply_to_id);
```

#### Database Management
- **Database Migrations** - Alembic for version control
- **Database Transactions** - ACID compliance for data integrity
- **Connection Pooling** - Efficient database connection management

### Caching & Queue System
- **Redis Integration** - Cache layer and message queue
- **User Data Cache** - Cache TMS user data (TTL: 5-15 min, key: `user:{tms_user_id}`)
- **Session Cache** - Cache user sessions (TTL: 24 hours)
- **Presence Cache** - Cache online/offline status (TTL: 5 min, key: `presence:{user_id}`)
- **Offline Message Queue** - Queue messages for offline users (Redis List)
- **Cache Invalidation** - Smart cache invalidation on TMS webhooks
- **Cache Warming** - Preload frequently accessed data (active conversations)

### WebSocket Management
- **WebSocket Server** - python-socketio with FastAPI
- **Connection Pooling** - Efficient connection management (max 10,000 concurrent)
- **Heartbeat/Ping-Pong** - Keep-alive every 30 seconds
- **Auto-Reconnection** - Client-side reconnection logic (exponential backoff)
- **Connection State** - Track connection states (connected, disconnected, reconnecting)
- **Message Broadcasting** - Efficient message delivery to conversation members
- **Room Management** - WebSocket rooms per conversation
- **Namespace Isolation** - Separate namespaces for messaging, calls, notifications

### Monitoring & Logging
- **Error Tracking** - Sentry for error tracking and alerting
- **Structured Logging** - JSON-formatted logs (timestamp, level, message, context)
- **Performance Monitoring** - Track API response times (p50, p95, p99)
- **Database Query Monitoring** - Identify slow queries (log queries >100ms)
- **WebSocket Monitoring** - Track connection health and message latency
- **Health Check Endpoints** - `/health` and `/health/ready` endpoints
- **Metrics Collection** - Prometheus metrics for Grafana dashboards

### Backup & Recovery
- **Database Backups** - Automated daily backups (Railway automatic)
- **Backup Strategy** - Daily full backup, keep last 7 days
- **Point-in-Time Recovery** - PostgreSQL WAL archiving
- **Disaster Recovery Plan** - Document recovery procedures
- **Data Retention Policy** - Messages: indefinite, Calls: 90 days, Logs: 30 days

---

## 🔒 Security

### API Security
- **Token Validation Middleware** - Validate TMS tokens on every request
- **Input Validation** - Validate all user inputs with Pydantic/Zod schemas
- **Input Sanitization** - Sanitize data to prevent injection attacks
- **SQL Injection Prevention** - Use SQLAlchemy ORM with parameterized queries
- **XSS Prevention** - Sanitize HTML/script content in messages
- **CSRF Protection** - CSRF tokens for state-changing operations
- **API Rate Limiting** - 100 requests/minute per user, 1000 requests/minute global
- **Request Size Limits** - Max 10MB per request

### Access Control
- **Permission-Based Access** - Role-based access control (RBAC)
- **Resource Authorization** - Verify user access to conversations/messages
- **Group Member Validation** - Verify group membership before allowing actions
- **Message Access Control** - Users can only access their conversation messages
- **File Access Control** - Secure file download URLs with signed tokens

### Network Security
- **CORS Configuration** - Whitelist TMS and TMA domains only
- **HTTPS Enforcement** - Force HTTPS for all connections
- **Secure Headers** - CSP, HSTS, X-Frame-Options, X-Content-Type-Options
- **IP Whitelisting** - Optional for admin endpoints
- **DDoS Protection** - Railway built-in + application-level rate limiting

### Data Security
- **Encryption at Rest** - Encrypt sensitive data in database (PostgreSQL pgcrypto)
- **Encryption in Transit** - TLS 1.3 for all communications
- **Secure File Storage** - Cloudinary with signed URLs
- **PII Protection** - Minimal PII storage (rely on TMS)

### Rate Limiting
- **Per-User Rate Limits** - 100 API calls/minute per tms_user_id
- **Per-Endpoint Limits** - Different limits for expensive endpoints
- **WebSocket Rate Limits** - Max 10 messages/second per user
- **File Upload Limits** - Max 5 uploads/minute per user, 10MB per file

---

## 👥 User Management

### User Profiles (View Only - Managed by TMS)
- **Profile Viewing** - View user profiles with TMS data
- **User Information Display** - Show username, email, position, avatar from TMS
- **User Search** - Search TMS users via TMS API
- **User Directory** - Browse organization users from TMS
- **Shared Groups** - View shared groups with a user

### User Status (TMA-Managed)
- **Online/Offline Status** - Real-time presence indicators (green dot)
- **Last Seen** - Last seen timestamp ("Last seen 2 hours ago")
- **Typing Indicators** - Show when user is typing ("John is typing...")
- **Active Status** - Show user activity in app

### User Blocking (TMA-Specific)
- **Block Users** - Block users from messaging
- **Unblock Users** - Unblock previously blocked users
- **Blocked Users List** - View list of blocked users in settings
- **Block Status Indicator** - Show if user is blocked in UI
- **Block Privacy** - Blocked users can't see online status or send messages

---

## 💬 Core Messaging

### Messaging Features
- **Direct Messaging** - One-on-one conversations
- **Group Chats** - Multi-user group conversations (max 256 members)
- **Real-time Messaging** - Instant message delivery via WebSocket
- **Message History** - Persistent message storage with infinite scroll
- **Offline Message Queue** - Queue and deliver messages when user comes online
- **Message Search** - Search messages within conversations

### Message Operations
- **Send Messages** - Send text, media, and file messages
- **Copy Message** - Copy message text to clipboard
- **Edit Messages** - Edit sent messages within 15 minutes (shows "edited" indicator)
- **Delete Messages** - Two options:
  - Delete for Me - Remove from your view only
  - Delete for Everyone - Remove for all participants (within 1 hour)
- **Forward Messages** - Forward messages to other conversations
- **Reply to Messages** - Reply/quote specific messages (shows original message)
- **Select Multiple Messages** - Bulk select for delete/forward
- **Pin Message** - Pin important message in chat (max 3 per conversation)
- **Message Reactions** - React with emojis to messages (max 12 unique reactions)
- **Message Info** - View delivery and read status details

### Message Status & Receipts
- **Message Status** - Visual indicators:
  - ⏱️ Sending (clock)
  - ✓ Sent (single gray check)
  - ✓✓ Delivered (double gray checks)
  - ✓✓ Read (double purple checks)
- **Read Receipts** - Show who read messages in group chats
- **Delivery Confirmation** - Confirm message delivery via WebSocket acknowledgment
- **Typing Indicators** - Real-time "User is typing..." status (3-dot animation)
- **Message Timestamps** - Show relative time ("Just now", "5m ago") and absolute on hover

---

## 📝 Message Content Types

### Text & Formatting
- **Text Messages** - Plain text messaging (max 10,000 characters)
- **Markdown Support** - Rich text formatting (**bold**, *italic*, `code`)
- **Emoji Support** - Full emoji support with emoji picker
- **Link Previews** - Auto-generate link previews with image/title
- **@Mentions** - Mention users in messages (triggers notification)

### Media Content
- **Image Attachments** - Share images (PNG, JPG, GIF, WebP, max 10MB)
- **Document Attachments** - Share documents (PDF, DOCX, XLSX, etc., max 10MB)
- **Voice Messages** - Record and send voice messages (max 5 minutes)
- **File Attachments** - General file attachments (max 10MB per file)

### Media Features
- **Image Optimization** - Automatic compression and resizing via Cloudinary
- **Image Viewer** - Full-screen image viewing with zoom/pan
- **Voice Playback** - Custom voice message player with progress bar
- **Waveform Visualization** - Audio waveform display for voice messages
- **File Preview** - Preview supported file types (images, PDFs)
- **Download Files** - Download attachments to device

---

## 💭 Message Display & UI

### Message Bubble Design
- **Viber-Style Bubbles** - Rounded corners with tail, purple for sent, gray for received
- **Message Grouping** - Group consecutive messages by same sender
- **Message Avatars** - User avatars in group conversations (left side for received)
- **Message Timestamps** - Time display for messages (relative and absolute)
- **Message Status Icons** - Visual checkmark status indicators
- **Edit Indicator** - Show "edited" label on edited messages
- **Reply Preview** - Show original message preview in replies
- **Pin Indicator** - Show pin icon on pinned messages

### Message Rendering
- **Virtualized Lists** - Performance-optimized rendering (react-window)
- **Lazy Loading** - Progressive image loading with blur placeholder
- **Auto-scroll** - Smart auto-scroll to new messages (only if near bottom)
- **Smooth Scrolling** - Smooth scroll behavior with CSS
- **Skeleton Screens** - Loading placeholders while fetching messages
- **Date Separators** - Show date dividers ("Today", "Yesterday", "Jan 15")
- **"New Messages" Divider** - Show divider line for unread messages
- **Scroll-to-Bottom Button** - Appears when scrolled up (shows unread count)

### Message Interactions
- **Long Press Menu** - Mobile long-press for actions (reply, forward, delete, copy)
- **Context Menu** - Right-click actions on desktop
- **Swipe Actions** - Swipe right to reply (mobile)
- **Quick Reactions** - Hover to show quick emoji reaction picker
- **Double-Tap to React** - Double-tap message to add heart reaction (mobile)

---

## 📞 Calls & WebRTC

### Call Types
- **Voice Calls** - One-on-one voice calls
- **Video Calls** - One-on-one video calls
- **Group Calls** - Multi-participant calls (Phase 2 - up to 8 participants)
- **Screen Share** - Share screen during calls (Phase 2)

### Call Management
- **Incoming Call Notifications** - Full-screen call UI with ringtone
- **Call Ringing** - Audio/visual ringing indicators
- **Call Accept/Decline** - Accept or reject incoming calls
- **Call End** - End active calls
- **Join Ongoing Calls** - Join in-progress group calls (Phase 2)
- **Active Call Management** - Track and display active calls
- **Busy Status** - Show "On a call" status when in call
- **Missed Call Notifications** - Notify and show missed calls in chat

### Call Controls
- **Audio Controls** - Mute/unmute microphone with visual indicator
- **Video Controls** - Enable/disable camera
- **Speaker Toggle** - Switch between speaker/earpiece (mobile)
- **Camera Switch** - Front/back camera toggle (mobile)
- **Video Quality Settings** - Adjust quality: Low (360p), Medium (480p), High (720p)
- **Volume Controls** - Adjust call volume

### Call Quality & Monitoring
- **Audio Level Indicators** - Visual audio level meters for participants
- **Call Health Monitoring** - Real-time connection quality indicator
- **Low-latency Optimizations** - WebRTC optimizations enabled
- **Echo Cancellation** - Built-in WebRTC audio echo cancellation
- **Noise Suppression** - Built-in WebRTC background noise reduction
- **Network Adaptation** - WebRTC automatically adapts to network (built-in)

### WebRTC Infrastructure
- **STUN/TURN Servers** - Free STUN (Google), TURN if needed (coturn on Railway)
- **ICE Candidates** - Connection negotiation via WebSocket signaling
- **Signaling Server** - WebSocket signaling for call setup/teardown
- **Media Stream Management** - Handle audio/video streams with error handling
- **Connection Recovery** - Attempt reconnection on network issues

### Call History
- **Call Records** - Complete call history in conversation
- **Call Duration** - Track and display call duration
- **Call Status** - Show completed, missed, declined, cancelled status
- **Call Traces** - Call history messages in conversation view
- **Call Participants** - List of call participants in history

---

## 🔐 End-to-End Encryption

**⚠️ Phase 3 Feature - Complex Implementation**

### Encryption Strategy

#### Phase 1 (MVP) - Basic Security
- **TLS/HTTPS** - Encryption in transit (enabled)
- **Database Encryption** - Encryption at rest for sensitive fields

#### Phase 2 - Enhanced Security
- **Server-Side Encryption** - Encrypt message content in database
- **Signed URLs** - Secure file access with expiring signed URLs
- **Key Derivation** - PBKDF2 for any password-related features

#### Phase 3 - Full E2EE (Future)
- **Signal Protocol** - Industry-standard E2EE protocol
- **Key Exchange** - X3DH key agreement protocol
- **Double Ratchet** - Forward secrecy
- **Device Management** - Multi-device support
- **Key Verification** - Safety number verification

### Current Implementation (Phase 1)
- **HTTPS Only** - All communications encrypted in transit
- **PostgreSQL pgcrypto** - Encrypt sensitive database fields
- **JWT Tokens** - Secure session management
- **File Encryption** - Cloudinary secure URLs with signed tokens

---

## 📊 Polls

### Poll Creation
- **Create Polls** - Create polls in conversations
- **Poll Questions** - Set poll question text (max 200 characters)
- **Poll Options** - Add 2-10 poll options (max 100 characters each)
- **Multiple Choice** - Allow multiple selections (optional)
- **Poll Expiration** - Set poll expiry time (optional: 1 hour, 1 day, 1 week)

### Poll Interaction
- **Vote on Polls** - Cast votes on poll options
- **Change Vote** - Modify previous votes (if poll not expired)
- **View Results** - Real-time poll results
- **Vote Counts** - See vote counts per option
- **Voter List** - See who voted (with avatars, unless anonymous)
- **Poll Notifications** - Notify when poll created/expires

### Poll Display
- **Progress Bars** - Visual vote distribution bars
- **Poll Status** - Active/expired status indicators
- **Total Votes** - Show total vote count
- **Percentage Display** - Show vote percentages
- **Poll in Message** - Poll appears as special message bubble

---

## 🔔 Notifications

### Notification Types
- **Message Notifications** - New message alerts
- **Call Notifications** - Incoming call alerts (highest priority)
- **Mention Notifications** - @mention alerts
- **Reaction Notifications** - Message reaction alerts
- **Group Activity** - Member added/removed notifications
- **Poll Notifications** - Poll creation/expiry alerts
- **Missed Call Notifications** - Missed call alerts

### Notification Delivery
- **Real-time Notifications** - Instant notification via WebSocket
- **Push Notifications** - Web push notification support (service worker)
- **Sound Notifications** - Audio alerts for different notification types
- **Badge Counts** - Unread count badges on app icon
- **Desktop Notifications** - Browser native notifications
- **In-App Notifications** - Toast messages for in-app events

### Notification Management
- **Notification Settings** - Global enable/disable notifications
- **Per-Conversation Settings** - Mute specific conversations
- **Mute Duration** - Mute for: 1 hour, 8 hours, 1 day, forever
- **Do Not Disturb** - DND mode (no sound, no visual notifications)
- **Notification Sounds** - Different sounds for messages, calls, mentions
- **Notification Previews** - Show/hide message content in notifications

### Notification UI
- **Toast Messages** - Non-intrusive in-app notifications (bottom-center)
- **Notification Badge** - Red badge with unread count on conversations
- **Sound Alerts** - Play sound on new notification
- **Vibration** - Haptic feedback on mobile

---

## 🔍 Search System

### Search Capabilities
- **Global Search** - Search across all conversations and messages
- **User Search** - Search TMS users via TMS API
- **Conversation Search** - Search and filter conversations
- **Message Search** - Full-text message search within conversation
- **File Search** - Search shared files/media
- **Search Filters** - Filter by date range, sender, type (text/image/file)

### Search Implementation
- **PostgreSQL Full-Text Search** - Built-in FTS with tsvector
- **Search Indexing** - Index message content and conversation names
- **Search Ranking** - Relevance-based ranking (ts_rank)
- **Search Highlighting** - Highlight search terms in results
- **Autocomplete** - Search suggestions as you type
- **Recent Searches** - Show recent search queries (client-side storage)

---

## ⚙️ Privacy & User Settings

**Note: User profile data (name, email, avatar) is managed by TMS**

### Privacy Controls
- **Last Seen Visibility** - Control who sees last seen:
  - Everyone (default)
  - Nobody
- **Online Status Visibility** - Control who sees online status (same options)
- **Read Receipt Settings** - Enable/disable read receipts (send and receive)
- **Typing Indicator Settings** - Enable/disable typing indicators (send and receive)
- **Block List Privacy** - Blocked users can't see your status or send messages

### User Preferences (TMA-Specific)
- **Notification Preferences** - Customize notification settings per type
- **Sound Settings** - Enable/disable sounds and choose notification tones
- **Auto-Download Media** - Control automatic media downloads (WiFi only, Always, Never)
- **Data Usage** - Control data-intensive features (video quality, auto-play)
- **Language** - App language selection (if implementing i18n)
- **Chat Background** - Choose chat background color/pattern

### Account Management
- **Data Export** - Export user data as JSON (GDPR compliance)
- **Clear Chat History** - Clear all message history (with confirmation)
- **Privacy Policy** - View privacy policy
- **Terms of Service** - View terms of service

---

## 🎨 UI/UX Features

### Theme System
- **Dark Mode** - Full dark theme with Viber colors
- **Light Mode** - Light theme (default)
- **System Theme** - Auto-detect system preference
- **Theme Persistence** - Remember theme preference (localStorage)
- **Theme Toggle** - Easy theme switching in settings

### Responsive Design
- **Mobile-First** - Optimized for mobile devices (320px+)
- **Tablet Support** - Responsive tablet layouts (768px+)
- **Desktop Optimization** - Full desktop experience (1024px+)
- **Touch Gestures** - Mobile touch interactions (swipe, long-press)
- **Haptic Feedback** - Vibration feedback on mobile actions
- **Adaptive Layouts** - Dynamic layout adjustments per screen size

### Accessibility
- **WCAG 2.1 AA Compliance** - Meet accessibility standards
- **Screen Reader Support** - Full screen reader compatibility (ARIA labels)
- **Focus Management** - Proper focus handling and visible focus indicators
- **ARIA Labels** - Comprehensive ARIA labeling on all interactive elements
- **Keyboard Navigation** - Full keyboard support (Tab, Enter, Esc, Arrow keys)
- **High Contrast Mode** - High contrast theme option

### Performance Optimizations
- **Lazy Loading** - Lazy load images and heavy components
- **Code Splitting** - Dynamic imports for route-based splitting
- **Image Optimization** - Automatic image optimization via Cloudinary
- **Virtualization** - Virtualized message lists (react-window)
- **Debouncing** - Debounce search inputs and typing indicators (300ms)
- **Auto-scroll** - Smart auto-scroll (only when near bottom)
- **Infinite Scroll** - Load more messages on scroll up
- **Service Workers** - PWA capabilities with caching strategy

### Visual Feedback
- **Loading States** - Loading spinners and indicators
- **Skeleton Screens** - Content placeholders while loading
- **Error States** - Clear error messaging with retry options
- **Success States** - Confirmation feedback (toasts)
- **Animations** - Smooth transitions (150ms-300ms)
- **Progress Indicators** - Show progress for uploads/downloads
- **Optimistic Updates** - Show actions immediately, rollback on error

### Error Handling
- **Error Boundaries** - Graceful error recovery with fallback UI
- **Call Error Boundary** - Specific error handling for call failures
- **Error Logging** - Log all errors to Sentry
- **User-Friendly Errors** - Clear, actionable error messages
- **Retry Mechanisms** - Auto-retry failed operations (max 3 retries)
- **Offline Detection** - Detect and show offline status

---

## 📁 File & Media Management

### File Uploads
- **Message Attachments** - Upload files in messages
- **Voice Message Upload** - Record and upload voice messages
- **Drag & Drop** - Drag and drop files into chat
- **File Type Validation** - Validate allowed file types
- **File Size Limits** - Enforce 10MB per file limit
- **Upload Progress** - Show progress bar during upload
- **Multiple Files** - Upload multiple files at once (max 10)

### Media Processing
- **Cloudinary Integration** - Cloud-based media storage and CDN
- **Image Optimization** - Automatic compression (quality: 80%)
- **Image Resizing** - Generate thumbnails (150px, 300px, 600px)
- **Image Formats** - Support PNG, JPG, GIF, WebP
- **Voice Encoding** - Encode voice messages to MP3/OGG
- **Thumbnail Generation** - Auto-generate thumbnails for images/videos

### Media Display
- **Image Viewer** - Full-screen image viewing with zoom/pan/swipe
- **Shared Media Gallery** - View all shared media in conversation
- **Media Grid** - Grid layout for media gallery
- **Voice Player** - Custom voice message player with waveform
- **Waveform Visualization** - Visual audio waveform
- **Lazy Image Loading** - Load images as they enter viewport

### File Management
- **File Storage** - Secure file storage on Cloudinary
- **Secure URLs** - Signed URLs with expiration (24 hours)
- **File Download** - Download attachments to device
- **CDN Delivery** - Fast global CDN delivery via Cloudinary

---

## 👥 Conversation Management

### Conversation Creation
- **New Direct Message** - Start new DM conversation with TMS user
- **Group Creation** - Create group conversation (select 2+ users)
- **User Selection** - Select users from TMS directory
- **Group Naming** - Set group name (required for groups)
- **Group Description** - Add group description (optional)
- **Group Avatar** - Set group avatar (upload or use default)

### Conversation Controls
- **Leave Conversation** - Leave group conversations (can't leave DMs)
- **Add Members** - Add users to groups (admin or members)
- **Remove Members** - Remove users from groups (admin only)
- **Member Management** - View and manage group members
- **Admin Promotion** - Group creator is admin (future: promote others)
- **Conversation Settings** - Access conversation settings panel
- **Mute Conversation** - Mute for 1h, 8h, 1 day, or forever
- **Clear History** - Clear conversation message history (local only)

### Conversation Display
- **Conversation List** - All conversations in sidebar (sorted by recent)
- **Conversation Search** - Search conversations by name
- **Conversation Avatars** - User avatar (DM) or group avatar
- **Last Message Preview** - Show last message and timestamp
- **Unread Count Badge** - Purple circle with unread count
- **Online Status Dot** - Green dot for online users (DMs only)
- **Conversation Sorting** - Sort by most recent activity
- **Pinned Conversations** - Pin important conversations to top (max 3)
- **Conversation Info Panel** - View members, shared media, settings

---

## 🛠️ DevOps & Testing

### CI/CD Pipeline
- **GitHub Actions** - Automated CI/CD workflows
- **Automated Testing** - Run tests on every push and PR
- **Build Pipeline** - Build and validate on every commit
- **Deployment Pipeline** - Auto-deploy to Railway on main branch merge
- **Environment Management** - Separate dev, staging, production environments
- **Rollback Strategy** - Quick rollback via Railway dashboard

### Testing Strategy
- **Unit Tests** - Component and function unit tests
  - Backend: pytest with pytest-cov (target: 80% coverage)
  - Frontend: Jest + React Testing Library (target: 70% coverage)
- **Integration Tests** - API and service integration tests
  - Test TMS API integration
  - Test database operations
  - Test WebSocket events
- **E2E Tests** - End-to-end user flow tests
  - Playwright for critical flows (send message, make call)
- **Load Testing** - Performance and load testing (Phase 2)
  - Locust for simulating concurrent users

### Monitoring & Analytics
- **Application Monitoring** - Uptime monitoring (Sentry performance)
- **Performance Monitoring** - Track response times and throughput
- **Error Rate Monitoring** - Track error rates and alert on spikes
- **User Analytics** - Privacy-respecting usage analytics (optional)
- **Custom Dashboards** - Grafana dashboards for metrics (Phase 2)

### Deployment
- **Railway Deployment** - Deploy backend and frontend to Railway
- **Environment Variables** - Manage via Railway dashboard and .env.example
- **Database Migrations** - Run Alembic migrations on deploy
- **Zero-Downtime Deploys** - Railway handles rolling deployments
- **Health Checks** - Pre-deployment health checks
- **Deployment Notifications** - Slack/email notifications on deploy

---

## 📋 Development Best Practices

### Code Quality
- **TypeScript** - Strict mode enabled, no any types
- **ESLint/Prettier** - Enforce code style and formatting
- **Code Reviews** - All PRs require review
- **Git Workflow** - Feature branch workflow (feature/*, bugfix/*)
- **Commit Conventions** - Conventional commits (feat, fix, docs, etc.)
- **Documentation** - Code comments and README for each module

### API Design
- **RESTful Standards** - Follow REST principles
- **API Versioning** - Version endpoints: `/api/v1/`
- **Consistent Responses** - Standard response format:
  ```json
  {
    "success": true,
    "data": {},
    "error": null
  }
  ```
- **Error Responses** - Consistent error format with error codes
- **Pagination** - Cursor-based pagination for lists
- **API Documentation** - Auto-generated docs via FastAPI (Swagger UI)

### Security Best Practices
- **Environment Secrets** - Never commit secrets (.env in .gitignore)
- **Least Privilege** - Minimum required permissions
- **Security Headers** - All recommended security headers
- **Dependency Scanning** - Dependabot alerts enabled
- **Regular Updates** - Keep dependencies updated monthly
- **Security Audits** - Quarterly security reviews

---

## 🗺️ Implementation Phases

### Phase 1: MVP (3-4 months)

**Goal:** Core messaging app with Viber UI

#### Month 1: Foundation
- Setup project structure (FastAPI + Next.js)
- Database schema and migrations
- TMS integration (auth, user sync)
- Redis caching setup
- Basic Viber UI components

#### Month 2: Core Messaging
- Direct messaging (send, receive, history)
- Group chats (create, add/remove members)
- WebSocket real-time messaging
- Message status (sent, delivered, read)
- Typing indicators
- File uploads (images, documents)

#### Month 3: Enhanced Messaging
- Message reactions
- Message replies
- Message editing/deleting
- Voice messages
- Link previews
- Search (messages, users, conversations)
- Notifications (web push, sounds)

#### Month 4: Calls & Polish
- Voice/video calls (1-on-1 via WebRTC)
- Call history
- User blocking
- Privacy settings
- Bug fixes and optimization
- Testing and deployment

**MVP Features:**
- ✅ TMS integration
- ✅ Direct messaging + Group chats
- ✅ Real-time messaging (WebSocket)
- ✅ Message reactions, replies, editing
- ✅ File sharing (images, documents)
- ✅ Voice messages
- ✅ Voice/video calls (1-on-1)
- ✅ Notifications
- ✅ Search
- ✅ User blocking
- ✅ Viber UI/theme
- ✅ Dark mode

---

### Phase 2: Enhanced Features (2-3 months)

**Goal:** Advanced features and improvements

#### Features:
- **Group Calls** - Multi-participant voice/video calls (up to 8)
- **Screen Share** - Share screen during calls
- **Polls** - Create and vote on polls
- **Message Forwarding** - Forward messages to multiple chats
- **Pin Messages** - Pin important messages in chat
- **Advanced Search** - Filters, date ranges, file search
- **Shared Media Gallery** - View all shared media per conversation
- **Chat Backgrounds** - Customizable chat backgrounds
- **Voice Call Quality** - Enhanced audio quality settings
- **Message Scheduling** - Schedule messages (future send)
- **Performance Optimizations** - Further optimizations
- **Load Testing** - Test with 1000+ concurrent users
- **Analytics Dashboard** - Usage analytics

---

### Phase 3: Advanced Security & Admin (2-3 months)

**Goal:** Enterprise-grade security and admin tools

#### Features:
- **Full E2EE** - Signal Protocol implementation
- **Multi-device Support** - Sync across multiple devices
- **Key Verification** - Safety number verification
- **Admin Dashboard** - Admin panel for user management
- **Content Moderation** - Report and moderate content
- **User Suspension** - Suspend/ban users
- **Audit Logs** - Track all admin actions
- **Advanced Analytics** - Detailed usage analytics
- **Data Export** - Bulk data export tools
- **Internationalization** - Multi-language support
- **Mobile Apps** - Native iOS/Android apps (React Native)

---

## 📊 Success Metrics

### Performance Targets
- **API Response Time:** p95 < 200ms
- **WebSocket Latency:** < 100ms
- **Message Delivery:** < 500ms end-to-end
- **Call Setup Time:** < 2 seconds
- **Page Load Time:** < 2 seconds (FCP)

### Reliability Targets
- **Uptime:** 99.9% (< 43 minutes downtime/month)
- **Error Rate:** < 0.1%
- **Database Queries:** < 100ms p95
- **WebSocket Reconnect:** < 5 seconds

### Scale Targets
- **Concurrent Users:** 1,000+ (MVP), 10,000+ (Phase 2)
- **Messages/Second:** 100+ (MVP), 1,000+ (Phase 2)
- **Database Size:** Handle 1M+ messages
- **File Storage:** 100GB+ (Cloudinary)

---

## 📚 Key Technical Decisions

### Why These Technologies?

**FastAPI:** Modern, fast, type-safe, excellent WebSocket support
**Next.js:** Best React framework, SSR/SSG, great DX
**PostgreSQL:** Reliable, full-text search, JSON support
**Redis:** Fast caching, pub/sub for WebSockets
**Cloudinary:** Managed media, automatic optimization
**Railway:** Easy deployment, database included
**Zustand:** Simpler than Redux, better DX
**shadcn/ui:** Copy-paste components, full customization
**Socket.io:** Reliable WebSocket with fallbacks

### Simplified Decisions

**No Microservices:** Start monolithic (simpler to develop and deploy)
**PostgreSQL FTS:** No need for ElasticSearch initially
**Simple Auth:** Rely on TMS (no custom auth needed)
**WebRTC Built-ins:** Use browser-native features (no custom VAD/noise suppression)
**No Custom Admin Panel (MVP):** Use database tools initially

---

## 🎯 Summary

This is a comprehensive plan for a **Viber-inspired team messaging app** that:
- ✅ Integrates with TMS for authentication and user data
- ✅ Provides real-time messaging with WebSocket
- ✅ Includes voice/video calls with WebRTC
- ✅ Features a complete Viber UI/UX design system
- ✅ Follows best practices and keeps things simple
- ✅ Has a clear 3-phase implementation roadmap
- ✅ Prioritizes MVP features and defers complex features

**Start with Phase 1 MVP**, get feedback, iterate, then move to Phase 2 and 3.
