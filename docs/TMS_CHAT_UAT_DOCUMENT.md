# TMS Chat - User Acceptance Testing (UAT) Document

**Version:** 1.0
**Date:** January 2026
**Application:** TMS Chat (Team Messaging System)
**Testing Environment:** Staging
**URL:** https://tms-chat-staging.example.com

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
3. [Test Case Instructions](#3-test-case-instructions)
4. [Test Cases](#4-test-cases)
   - [Module 1: Login & Authentication](#module-1-login--authentication)
   - [Module 2: Conversations](#module-2-conversations)
   - [Module 3: Messaging](#module-3-messaging)
   - [Module 4: File Sharing](#module-4-file-sharing)
   - [Module 5: Polls](#module-5-polls)
   - [Module 6: Reactions & Emoji](#module-6-reactions--emoji)
   - [Module 7: Search](#module-7-search)
   - [Module 8: Notifications](#module-8-notifications)
   - [Module 9: Settings & Preferences](#module-9-settings--preferences)
   - [Module 10: Real-time Features](#module-10-real-time-features)
5. [Test Result Summary Sheet](#5-test-result-summary-sheet)
6. [Issue Reporting Guidelines](#6-issue-reporting-guidelines)
7. [Glossary](#7-glossary)

---

## 1. Introduction

### Purpose
This document provides step-by-step test cases for general users to verify that the TMS Chat application works correctly and meets user expectations.

### What is TMS Chat?
TMS Chat is a team messaging application (similar to Viber or Messenger) that allows you to:
- Send instant messages to colleagues
- Create group conversations
- Share files and images
- Create polls for team decisions
- React to messages with emoji
- Search through message history

### Who Should Use This Document?
This UAT is designed for general users with no technical background. You only need:
- A computer or mobile device with internet access
- A web browser (Chrome, Firefox, Safari, or Edge recommended)
- Your GCGC Team Management System account credentials

### Testing Period
**Start Date:** _______________
**End Date:** _______________

### Support Contact
If you encounter issues during testing, please contact:
- **Email:** _______________
- **Phone:** _______________

---

## 2. Getting Started

### Prerequisites
Before starting the tests, ensure you have:

| Requirement | Details |
|-------------|---------|
| Web Browser | Chrome, Firefox, Safari, or Edge (latest version) |
| Internet Connection | Stable internet connection |
| GCGC Account | Active account in GCGC Team Management System |
| Test Partner | Another user to test real-time messaging features |

### Accessing TMS Chat

**Staging Environment (for testing):**
```
https://tms-chat-staging.example.com
```

**Production Environment (after UAT approval):**
```
https://tms-chat.example.com
```

### Browser Recommendations
For the best experience, we recommend:
- **Desktop:** Google Chrome or Microsoft Edge
- **Mobile:** Chrome (Android) or Safari (iOS)

---

## 3. Test Case Instructions

### How to Read Test Cases

Each test case contains:

| Field | Description |
|-------|-------------|
| **Test ID** | Unique identifier (e.g., TC-001) |
| **Test Name** | Brief description of what is being tested |
| **Preconditions** | What must be true before starting the test |
| **Steps** | Numbered actions to perform |
| **Expected Result** | What should happen if the feature works correctly |
| **Your Result** | Your observation (Pass/Fail/Blocked) |
| **Comments** | Space for your notes or issues found |

### Result Options

| Result | When to Use |
|--------|-------------|
| **PASS** | The feature works exactly as described in Expected Result |
| **FAIL** | The feature does not work as expected or produces an error |
| **BLOCKED** | You cannot perform the test due to a previous failure or missing prerequisite |
| **N/A** | The test does not apply to your situation |

### Tips for Effective Testing
1. Follow the steps in order
2. Do not skip steps
3. Note exactly what happened, especially if it differs from expected
4. Take screenshots of errors if possible
5. Record the time when issues occur
6. Test on different devices if available (desktop + mobile)

---

## 4. Test Cases

---

## Module 1: Login & Authentication

### TC-001: Login via GCGC SSO

| Field | Details |
|-------|---------|
| **Test ID** | TC-001 |
| **Test Name** | Login to TMS Chat using GCGC credentials |
| **Priority** | High |
| **Preconditions** | You have an active GCGC account |

**Steps:**
1. Open your web browser
2. Navigate to `https://tms-chat-staging.example.com`
3. You should be automatically redirected to the GCGC login page
4. Enter your GCGC username/email
5. Enter your GCGC password
6. Click the "Login" or "Sign In" button

**Expected Result:**
- You are redirected back to TMS Chat
- The main chat interface loads
- Your name and avatar appear in the top right corner
- The conversation list is displayed

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-002: View User Profile

| Field | Details |
|-------|---------|
| **Test ID** | TC-002 |
| **Test Name** | View your profile information |
| **Priority** | Medium |
| **Preconditions** | You are logged into TMS Chat |

**Steps:**
1. Click on your avatar or name in the top right corner
2. Click "Profile" or "Settings" from the dropdown menu
3. View your profile information

**Expected Result:**
- Your profile page displays:
  - Your full name
  - Your email address
  - Your role (e.g., MEMBER, LEADER, ADMIN)
  - Your department/division information
  - Your profile picture

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-003: Logout

| Field | Details |
|-------|---------|
| **Test ID** | TC-003 |
| **Test Name** | Logout from TMS Chat |
| **Priority** | High |
| **Preconditions** | You are logged into TMS Chat |

**Steps:**
1. Click on your avatar in the top right corner
2. Click "Logout" from the dropdown menu
3. Confirm logout if prompted

**Expected Result:**
- You are logged out of TMS Chat
- You are redirected to the login page or GCGC login
- Your session is ended

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-004: Session Persistence

| Field | Details |
|-------|---------|
| **Test ID** | TC-004 |
| **Test Name** | Stay logged in after closing browser tab |
| **Priority** | Medium |
| **Preconditions** | You are logged into TMS Chat |

**Steps:**
1. While logged in, note your current conversations
2. Close the browser tab (not the entire browser)
3. Open a new tab
4. Navigate to `https://tms-chat-staging.example.com`

**Expected Result:**
- You are still logged in
- Your conversations are visible
- You do not need to login again

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

## Module 2: Conversations

### TC-005: View Conversation List

| Field | Details |
|-------|---------|
| **Test ID** | TC-005 |
| **Test Name** | View all your conversations |
| **Priority** | High |
| **Preconditions** | You are logged into TMS Chat |

**Steps:**
1. Look at the left side panel of the screen
2. Observe the list of conversations

**Expected Result:**
- Conversation list is visible on the left side
- Each conversation shows:
  - Contact name or group name
  - Profile picture or group avatar
  - Preview of the last message
  - Time of last message
  - Unread message count (if any)

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-006: Create Direct Message (DM) Conversation

| Field | Details |
|-------|---------|
| **Test ID** | TC-006 |
| **Test Name** | Start a new direct message with another user |
| **Priority** | High |
| **Preconditions** | You are logged into TMS Chat; You know another user in the system |

**Steps:**
1. Click the "+" button or "New Conversation" button
2. Select "Direct Message" or "New Chat" option
3. Search for a colleague by name or email
4. Click on their name to select them
5. Click "Create" or "Start Chat"

**Expected Result:**
- A new conversation is created
- The conversation appears in your list
- You can see the chat area ready for typing
- The other person's name appears as the conversation title

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-007: Create Group Conversation

| Field | Details |
|-------|---------|
| **Test ID** | TC-007 |
| **Test Name** | Create a new group chat with multiple users |
| **Priority** | High |
| **Preconditions** | You are logged into TMS Chat; You know at least 2 other users |

**Steps:**
1. Click the "+" button or "New Conversation" button
2. Select "New Group" option
3. Enter a group name (e.g., "UAT Test Group")
4. Search and select at least 2 colleagues
5. Click "Create Group" or "Create"

**Expected Result:**
- A new group conversation is created
- The group appears in your conversation list
- The group name you entered is displayed
- All selected members are added to the group

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-008: View Conversation Details

| Field | Details |
|-------|---------|
| **Test ID** | TC-008 |
| **Test Name** | View details of a conversation |
| **Priority** | Medium |
| **Preconditions** | You have at least one group conversation |

**Steps:**
1. Click on a group conversation to open it
2. Click on the group name at the top of the chat
3. Or click the info/settings icon (usually "⋮" or "i")
4. View the conversation details

**Expected Result:**
- Conversation details panel opens showing:
  - Group name (for groups)
  - Group avatar (for groups)
  - List of members with their names
  - Member roles (Admin, Member)
  - Options to manage the conversation

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-009: Add Members to Group (Admin Only)

| Field | Details |
|-------|---------|
| **Test ID** | TC-009 |
| **Test Name** | Add new members to an existing group |
| **Priority** | Medium |
| **Preconditions** | You are an admin of a group conversation |

**Steps:**
1. Open a group conversation where you are an admin
2. Click on the group name or settings icon
3. Click "Add Members" option
4. Search for a colleague to add
5. Select the person and click "Add"

**Expected Result:**
- The new member is added to the group
- A system message appears: "[Name] was added to the group"
- The member count increases
- The new member can now see and participate in the conversation

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED  ☐ N/A (not admin) | |

---

### TC-010: Remove Member from Group (Admin Only)

| Field | Details |
|-------|---------|
| **Test ID** | TC-010 |
| **Test Name** | Remove a member from a group |
| **Priority** | Medium |
| **Preconditions** | You are an admin of a group with at least 3 members |

**Steps:**
1. Open a group conversation where you are an admin
2. Click on the group name or settings icon
3. Find the member you want to remove
4. Click "Remove" or the remove icon next to their name
5. Confirm the removal if prompted

**Expected Result:**
- The member is removed from the group
- A system message appears: "[Name] was removed from the group"
- The member count decreases
- The removed member can no longer see new messages

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED  ☐ N/A (not admin) | |

---

### TC-011: Leave a Group Conversation

| Field | Details |
|-------|---------|
| **Test ID** | TC-011 |
| **Test Name** | Leave a group conversation voluntarily |
| **Priority** | Medium |
| **Preconditions** | You are a member of a group conversation |

**Steps:**
1. Open a group conversation
2. Click on the group name or settings icon
3. Click "Leave Group" or "Leave Conversation"
4. Confirm your decision if prompted

**Expected Result:**
- You are removed from the group
- The group disappears from your conversation list
- A system message appears for other members: "[Your name] left the group"
- You can no longer see or send messages in that group

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-012: Edit Group Name (Admin Only)

| Field | Details |
|-------|---------|
| **Test ID** | TC-012 |
| **Test Name** | Change the name of a group conversation |
| **Priority** | Low |
| **Preconditions** | You are an admin of a group conversation |

**Steps:**
1. Open a group conversation where you are an admin
2. Click on the group name or settings icon
3. Click "Edit" next to the group name
4. Enter a new group name
5. Save the changes

**Expected Result:**
- The group name is updated
- The new name appears in the conversation list
- Other members see the updated name
- A system message may appear: "Group name changed to [new name]"

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED  ☐ N/A (not admin) | |

---

### TC-013: Mute a Conversation

| Field | Details |
|-------|---------|
| **Test ID** | TC-013 |
| **Test Name** | Mute notifications for a conversation |
| **Priority** | Medium |
| **Preconditions** | You have at least one conversation |

**Steps:**
1. Click on a conversation to select it
2. Click on the conversation settings (⋮ or right-click)
3. Click "Mute" or "Mute Notifications"
4. Select mute duration if options are available (e.g., 1 hour, 8 hours, forever)

**Expected Result:**
- The conversation is muted
- A muted icon appears on the conversation
- You no longer receive sound/popup notifications for this conversation
- Messages still appear when you open the conversation

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

## Module 3: Messaging

### TC-014: Send a Text Message

| Field | Details |
|-------|---------|
| **Test ID** | TC-014 |
| **Test Name** | Send a basic text message |
| **Priority** | High |
| **Preconditions** | You have at least one conversation |

**Steps:**
1. Click on a conversation to open it
2. Click in the message input box at the bottom
3. Type a message: "Hello, this is a test message"
4. Press Enter or click the Send button

**Expected Result:**
- The message appears in the chat immediately
- The message shows as "sent" (single checkmark or similar indicator)
- The message appears on the right side (your messages)
- The timestamp is shown

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-015: Receive a Text Message

| Field | Details |
|-------|---------|
| **Test ID** | TC-015 |
| **Test Name** | Receive a message from another user |
| **Priority** | High |
| **Preconditions** | You have a test partner who can send you a message |

**Steps:**
1. Open a conversation with your test partner
2. Ask your test partner to send you a message
3. Wait for the message to arrive

**Expected Result:**
- The message appears in the chat in real-time (no refresh needed)
- The message appears on the left side (received messages)
- A notification sound plays (if notifications are enabled)
- The sender's name/avatar is shown (in group chats)

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-016: Message Delivery Status

| Field | Details |
|-------|---------|
| **Test ID** | TC-016 |
| **Test Name** | Verify message delivery and read status |
| **Priority** | Medium |
| **Preconditions** | You have a test partner online |

**Steps:**
1. Send a message to your test partner
2. Observe the status indicator on your message
3. Ask your test partner to open the conversation and read the message
4. Observe if the status changes

**Expected Result:**
- Initially: Message shows "sent" status (✓)
- After delivery: Message shows "delivered" status (✓✓)
- After read: Message shows "read" status (blue ✓✓ or "seen")

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-017: Edit a Message

| Field | Details |
|-------|---------|
| **Test ID** | TC-017 |
| **Test Name** | Edit a message you sent |
| **Priority** | Medium |
| **Preconditions** | You have sent at least one message |

**Steps:**
1. Find a message you sent
2. Hover over the message or long-press (mobile)
3. Click the "Edit" option (pencil icon or from menu)
4. Modify the message text
5. Save the changes (press Enter or click Save)

**Expected Result:**
- The message is updated with new text
- An "edited" label appears on the message
- Other users see the updated message
- The original timestamp is preserved

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-018: Delete a Message

| Field | Details |
|-------|---------|
| **Test ID** | TC-018 |
| **Test Name** | Delete a message you sent |
| **Priority** | Medium |
| **Preconditions** | You have sent at least one message |

**Steps:**
1. Find a message you sent
2. Hover over the message or long-press (mobile)
3. Click the "Delete" option (trash icon or from menu)
4. Confirm deletion if prompted

**Expected Result:**
- The message is removed from the conversation
- Other users can no longer see the message
- The message is replaced with "Message deleted" or removed entirely

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-019: Reply to a Message

| Field | Details |
|-------|---------|
| **Test ID** | TC-019 |
| **Test Name** | Reply to a specific message |
| **Priority** | Medium |
| **Preconditions** | There are messages in a conversation |

**Steps:**
1. Find a message you want to reply to
2. Hover over the message or long-press (mobile)
3. Click the "Reply" option
4. Type your reply message
5. Send the reply

**Expected Result:**
- A preview of the original message appears above your input
- Your reply is sent with a link to the original message
- The reply shows what message it's responding to
- Clicking the reference scrolls to the original message

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-020: Send Long Message

| Field | Details |
|-------|---------|
| **Test ID** | TC-020 |
| **Test Name** | Send a message with multiple lines and paragraphs |
| **Priority** | Low |
| **Preconditions** | You have a conversation open |

**Steps:**
1. Click in the message input box
2. Type a long message with multiple lines:
   ```
   This is line 1.
   This is line 2.

   This is a new paragraph.
   Testing long messages.
   ```
3. Use Shift+Enter for new lines (if Enter sends message)
4. Send the message

**Expected Result:**
- The message is sent with line breaks preserved
- Multiple paragraphs are displayed correctly
- The message is readable and formatted properly

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

## Module 4: File Sharing

### TC-021: Upload and Send an Image

| Field | Details |
|-------|---------|
| **Test ID** | TC-021 |
| **Test Name** | Share an image in a conversation |
| **Priority** | High |
| **Preconditions** | You have an image file (JPG, PNG) ready |

**Steps:**
1. Open a conversation
2. Click the attachment/file button (📎 or + icon)
3. Select an image file from your device
4. Wait for upload to complete
5. Send the message

**Expected Result:**
- Upload progress is shown
- The image appears in the chat
- The image displays as a thumbnail
- Clicking the image opens a larger preview
- Other users can see the image

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-022: Upload and Send a Document

| Field | Details |
|-------|---------|
| **Test ID** | TC-022 |
| **Test Name** | Share a document (PDF, Word) in a conversation |
| **Priority** | High |
| **Preconditions** | You have a document file (PDF, DOCX) ready |

**Steps:**
1. Open a conversation
2. Click the attachment/file button
3. Select a document file (PDF or Word)
4. Wait for upload to complete
5. Send the message

**Expected Result:**
- Upload progress is shown
- The document appears with a file icon
- File name and size are displayed
- Clicking the file downloads or opens it
- Other users can access the file

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-023: Download a Shared File

| Field | Details |
|-------|---------|
| **Test ID** | TC-023 |
| **Test Name** | Download a file shared by another user |
| **Priority** | High |
| **Preconditions** | Another user has shared a file with you |

**Steps:**
1. Find a message containing a shared file
2. Click on the file or download button
3. Wait for the download to complete
4. Open the downloaded file

**Expected Result:**
- The file downloads successfully
- The downloaded file can be opened
- The file content matches what was uploaded
- No errors occur during download

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-024: View Image in Full Screen

| Field | Details |
|-------|---------|
| **Test ID** | TC-024 |
| **Test Name** | View a shared image in full screen mode |
| **Priority** | Low |
| **Preconditions** | There is an image in a conversation |

**Steps:**
1. Find an image message in a conversation
2. Click on the image thumbnail
3. View the image in full screen/lightbox mode
4. Close the full screen view

**Expected Result:**
- Image opens in a larger view/lightbox
- Image quality is clear and readable
- You can close the view by clicking X or outside the image
- You return to the conversation after closing

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-025: File Size Limit Validation

| Field | Details |
|-------|---------|
| **Test ID** | TC-025 |
| **Test Name** | Verify file size limit is enforced |
| **Priority** | Medium |
| **Preconditions** | You have a large file (>100MB for documents) |

**Steps:**
1. Open a conversation
2. Try to upload a file larger than the allowed limit
3. Observe the result

**Expected Result:**
- An error message appears indicating the file is too large
- The file is not uploaded
- The message shows the maximum allowed file size
- The application does not crash

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

## Module 5: Polls

### TC-026: Create a Poll

| Field | Details |
|-------|---------|
| **Test ID** | TC-026 |
| **Test Name** | Create a new poll in a group conversation |
| **Priority** | Medium |
| **Preconditions** | You are in a group conversation |

**Steps:**
1. Open a group conversation
2. Click the "+" or attachment button
3. Select "Create Poll" option
4. Enter a poll question: "What day works best for the meeting?"
5. Add options: "Monday", "Tuesday", "Wednesday"
6. Choose poll settings (single/multiple choice)
7. Click "Create" or "Send Poll"

**Expected Result:**
- The poll appears in the conversation
- All options are displayed
- The question is shown clearly
- Other members can see the poll

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-027: Vote on a Poll

| Field | Details |
|-------|---------|
| **Test ID** | TC-027 |
| **Test Name** | Cast a vote on an existing poll |
| **Priority** | Medium |
| **Preconditions** | There is an active poll in a conversation |

**Steps:**
1. Find a poll in a conversation
2. Click on one of the poll options to vote
3. Observe the result

**Expected Result:**
- Your vote is recorded
- The vote count updates
- Your selection is highlighted
- A progress bar shows the percentage of votes

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-028: Change Vote on a Poll

| Field | Details |
|-------|---------|
| **Test ID** | TC-028 |
| **Test Name** | Change your vote on a poll |
| **Priority** | Low |
| **Preconditions** | You have already voted on a poll |

**Steps:**
1. Find a poll you have already voted on
2. Click on a different option
3. Observe the result

**Expected Result:**
- Your previous vote is removed
- Your new vote is recorded
- Vote counts update accordingly
- Only one vote per user (for single-choice polls)

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-029: View Poll Results

| Field | Details |
|-------|---------|
| **Test ID** | TC-029 |
| **Test Name** | View who voted for each option |
| **Priority** | Low |
| **Preconditions** | There is a poll with votes |

**Steps:**
1. Find a poll with votes
2. Click on a poll option or "View Results"
3. View the list of voters

**Expected Result:**
- You can see who voted for each option
- Vote counts are accurate
- Percentages are calculated correctly
- All voters are listed

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-030: Close a Poll (Creator Only)

| Field | Details |
|-------|---------|
| **Test ID** | TC-030 |
| **Test Name** | Close a poll you created |
| **Priority** | Low |
| **Preconditions** | You created an active poll |

**Steps:**
1. Find a poll you created
2. Click the "Close Poll" option
3. Confirm if prompted

**Expected Result:**
- The poll is marked as closed
- No more votes can be cast
- Final results are displayed
- Other users see the poll as closed

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED  ☐ N/A (not poll creator) | |

---

## Module 6: Reactions & Emoji

### TC-031: Add Reaction to a Message

| Field | Details |
|-------|---------|
| **Test ID** | TC-031 |
| **Test Name** | React to a message with an emoji |
| **Priority** | Medium |
| **Preconditions** | There is a message in a conversation |

**Steps:**
1. Find a message in a conversation
2. Hover over the message (desktop) or long-press (mobile)
3. Click on a reaction emoji (e.g., 👍, ❤️, 😂)
4. Or click the emoji picker to choose a different reaction

**Expected Result:**
- The emoji appears below the message
- The reaction count shows "1"
- Your reaction is highlighted/selected
- Other users can see your reaction

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-032: Remove Reaction from a Message

| Field | Details |
|-------|---------|
| **Test ID** | TC-032 |
| **Test Name** | Remove your reaction from a message |
| **Priority** | Low |
| **Preconditions** | You have reacted to a message |

**Steps:**
1. Find a message you have reacted to
2. Click on your reaction emoji again
3. Observe the result

**Expected Result:**
- Your reaction is removed
- The reaction count decreases or disappears
- The reaction is no longer highlighted

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-033: Send Message with Emoji

| Field | Details |
|-------|---------|
| **Test ID** | TC-033 |
| **Test Name** | Insert emoji into a message using emoji picker |
| **Priority** | Low |
| **Preconditions** | You have a conversation open |

**Steps:**
1. Click in the message input box
2. Click the emoji button (😀 icon)
3. Browse or search for an emoji
4. Click on an emoji to insert it
5. Add some text and send the message

**Expected Result:**
- Emoji picker opens when clicked
- You can browse emoji categories
- Selected emoji is inserted at cursor position
- Message sends with the emoji displayed correctly

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

## Module 7: Search

### TC-034: Search Conversations by Name

| Field | Details |
|-------|---------|
| **Test ID** | TC-034 |
| **Test Name** | Search for a conversation by name |
| **Priority** | High |
| **Preconditions** | You have multiple conversations |

**Steps:**
1. Find the search box in the conversation list area
2. Type a contact name or group name
3. Observe the filtered results

**Expected Result:**
- Conversations filter as you type
- Matching conversations are shown
- Non-matching conversations are hidden
- Clearing the search shows all conversations

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-035: Search Messages Within a Conversation

| Field | Details |
|-------|---------|
| **Test ID** | TC-035 |
| **Test Name** | Search for specific text within a conversation |
| **Priority** | Medium |
| **Preconditions** | You have a conversation with multiple messages |

**Steps:**
1. Open a conversation
2. Click the search icon in the chat header
3. Type a word that exists in a message
4. Press Enter or click Search

**Expected Result:**
- Search results show messages containing the word
- You can navigate between results (next/previous)
- Clicking a result scrolls to that message
- The search term is highlighted in the message

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-036: Search All Conversations (Unified Search)

| Field | Details |
|-------|---------|
| **Test ID** | TC-036 |
| **Test Name** | Search for messages across all conversations |
| **Priority** | Medium |
| **Preconditions** | You have messages in multiple conversations |

**Steps:**
1. Look for a global/unified search option
2. Type a search term that might be in multiple conversations
3. View the search results

**Expected Result:**
- Results from multiple conversations are shown
- Each result shows which conversation it's from
- Clicking a result opens that conversation
- The message is highlighted or scrolled into view

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

## Module 8: Notifications

### TC-037: Receive Browser Notification

| Field | Details |
|-------|---------|
| **Test ID** | TC-037 |
| **Test Name** | Receive a browser notification for new message |
| **Priority** | Medium |
| **Preconditions** | Browser notifications are enabled; TMS Chat tab is in background |

**Steps:**
1. Ensure browser notifications are allowed for TMS Chat
2. Minimize the browser or switch to another tab
3. Have your test partner send you a message
4. Observe if a browser notification appears

**Expected Result:**
- A browser notification pops up
- The notification shows the sender name
- The notification shows a message preview
- Clicking the notification opens TMS Chat

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-038: Receive Sound Notification

| Field | Details |
|-------|---------|
| **Test ID** | TC-038 |
| **Test Name** | Hear a sound when receiving a new message |
| **Priority** | Low |
| **Preconditions** | Sound notifications are enabled; Your device volume is on |

**Steps:**
1. Open TMS Chat with another conversation visible
2. Have your test partner send you a message
3. Listen for a notification sound

**Expected Result:**
- A notification sound plays when message arrives
- The sound is audible and recognizable
- Sound only plays for new messages (not your own)

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-039: View Unread Message Badge

| Field | Details |
|-------|---------|
| **Test ID** | TC-039 |
| **Test Name** | See unread message count on conversations |
| **Priority** | High |
| **Preconditions** | You have unread messages |

**Steps:**
1. Have your test partner send you 3 messages while you're in a different conversation
2. Look at the conversation list
3. Find the conversation with new messages

**Expected Result:**
- A badge/number shows the unread count (e.g., "3")
- The badge is clearly visible
- Opening the conversation clears the badge
- The badge updates in real-time

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

## Module 9: Settings & Preferences

### TC-040: Change Theme (Dark/Light Mode)

| Field | Details |
|-------|---------|
| **Test ID** | TC-040 |
| **Test Name** | Switch between light and dark mode |
| **Priority** | Low |
| **Preconditions** | You are logged into TMS Chat |

**Steps:**
1. Click on your avatar or settings icon
2. Find the theme option (sun/moon icon or in settings)
3. Click to toggle between Light, Dark, or System mode
4. Observe the interface change

**Expected Result:**
- The interface changes color theme immediately
- Dark mode: Dark background, light text
- Light mode: Light background, dark text
- System mode: Follows your device setting
- Preference is saved for next visit

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-041: Configure Notification Settings

| Field | Details |
|-------|---------|
| **Test ID** | TC-041 |
| **Test Name** | Change notification preferences |
| **Priority** | Medium |
| **Preconditions** | You are logged into TMS Chat |

**Steps:**
1. Click on your avatar or settings
2. Navigate to Notification Settings
3. Toggle the following options:
   - Sound notifications
   - Browser notifications
   - Message notifications
4. Save changes if required

**Expected Result:**
- Settings are saved successfully
- Toggling off sounds stops notification sounds
- Toggling off browser notifications stops popups
- Settings persist after page refresh

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-042: Set Do Not Disturb Schedule

| Field | Details |
|-------|---------|
| **Test ID** | TC-042 |
| **Test Name** | Configure Do Not Disturb (DND) time |
| **Priority** | Low |
| **Preconditions** | You are in notification settings |

**Steps:**
1. Navigate to Notification Settings
2. Find "Do Not Disturb" or "DND" option
3. Enable DND
4. Set start time (e.g., 10:00 PM)
5. Set end time (e.g., 7:00 AM)
6. Save the settings

**Expected Result:**
- DND settings are saved
- During DND hours, notifications are silenced
- Outside DND hours, notifications work normally
- DND icon may appear during active hours

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

## Module 10: Real-time Features

### TC-043: Real-time Message Delivery

| Field | Details |
|-------|---------|
| **Test ID** | TC-043 |
| **Test Name** | Messages appear instantly without refresh |
| **Priority** | High |
| **Preconditions** | You and your test partner are both online |

**Steps:**
1. Open a conversation with your test partner
2. Both of you should have the conversation open
3. Your partner sends a message
4. Observe how quickly the message appears

**Expected Result:**
- Message appears within 1-2 seconds
- No page refresh is required
- Message smoothly appears in the chat
- No duplicated messages

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-044: Online/Offline Status

| Field | Details |
|-------|---------|
| **Test ID** | TC-044 |
| **Test Name** | See when contacts are online or offline |
| **Priority** | Medium |
| **Preconditions** | You have a test partner who can go online/offline |

**Steps:**
1. Note your test partner's online status (green dot or "online" indicator)
2. Ask your test partner to log out or close TMS Chat
3. Observe if their status changes to offline
4. Ask them to log back in
5. Observe if their status changes to online

**Expected Result:**
- Online users show a green dot or "Online" status
- Offline users show no dot or "Offline" / "Last seen" status
- Status updates within a few seconds
- Status is visible in conversation list and chat header

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-045: Connection Status Indicator

| Field | Details |
|-------|---------|
| **Test ID** | TC-045 |
| **Test Name** | See when connection to server is lost |
| **Priority** | Medium |
| **Preconditions** | You are logged into TMS Chat |

**Steps:**
1. Disconnect your internet (turn off WiFi or unplug ethernet)
2. Observe the TMS Chat interface
3. Reconnect your internet
4. Observe the reconnection

**Expected Result:**
- When disconnected: A warning appears (e.g., "Connection lost" or red indicator)
- Messages cannot be sent while disconnected
- When reconnected: Warning disappears, connection resumes
- Any queued messages are sent after reconnection

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-046: Simultaneous Users in Conversation

| Field | Details |
|-------|---------|
| **Test ID** | TC-046 |
| **Test Name** | Multiple users chatting simultaneously |
| **Priority** | High |
| **Preconditions** | You have at least 2 test partners; All are in a group conversation |

**Steps:**
1. Open a group conversation with 3+ members (including yourself)
2. Have all members send messages at roughly the same time
3. Observe that all messages appear for everyone

**Expected Result:**
- All messages appear for all users
- Messages are in correct chronological order
- No messages are lost or duplicated
- All users see the same conversation history

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

### TC-047: Reaction Updates in Real-time

| Field | Details |
|-------|---------|
| **Test ID** | TC-047 |
| **Test Name** | See reactions update in real-time |
| **Priority** | Low |
| **Preconditions** | You and test partner are viewing the same conversation |

**Steps:**
1. Open a conversation with your test partner
2. Both of you view the same message
3. Your partner adds a reaction to a message
4. Observe if the reaction appears without refresh

**Expected Result:**
- Reaction appears immediately for both users
- Reaction count updates in real-time
- No page refresh needed

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED | |

---

## Mobile-Specific Tests (If Testing on Mobile)

### TC-048: Mobile Responsive Layout

| Field | Details |
|-------|---------|
| **Test ID** | TC-048 |
| **Test Name** | Application works on mobile devices |
| **Priority** | Medium |
| **Preconditions** | You have a mobile phone or tablet |

**Steps:**
1. Open TMS Chat on your mobile browser
2. Navigate through the application
3. Try sending a message
4. Try opening different conversations

**Expected Result:**
- Interface adapts to mobile screen size
- All buttons and text are readable
- Touch interactions work (tap, swipe)
- Keyboard appears for typing
- All core features are accessible

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED  ☐ N/A (no mobile device) | |

---

### TC-049: Mobile Navigation

| Field | Details |
|-------|---------|
| **Test ID** | TC-049 |
| **Test Name** | Navigate between conversations on mobile |
| **Priority** | Medium |
| **Preconditions** | You are using TMS Chat on mobile |

**Steps:**
1. View the conversation list
2. Tap on a conversation to open it
3. Find and tap the back button
4. Verify you return to the conversation list

**Expected Result:**
- Tapping a conversation opens the chat view
- Back button is visible and accessible
- Back button returns to conversation list
- Smooth transitions between views

| Your Result | Comments |
|-------------|----------|
| ☐ PASS  ☐ FAIL  ☐ BLOCKED  ☐ N/A (no mobile device) | |

---

## 5. Test Result Summary Sheet

Please complete this summary after finishing all test cases.

### Tester Information

| Field | Your Response |
|-------|---------------|
| **Tester Name** | |
| **Department** | |
| **Test Date(s)** | |
| **Device Used** | |
| **Browser Used** | |
| **Browser Version** | |

### Test Results Summary

| Module | Total Tests | Passed | Failed | Blocked | N/A |
|--------|-------------|--------|--------|---------|-----|
| 1. Login & Authentication | 4 | | | | |
| 2. Conversations | 9 | | | | |
| 3. Messaging | 7 | | | | |
| 4. File Sharing | 5 | | | | |
| 5. Polls | 5 | | | | |
| 6. Reactions & Emoji | 3 | | | | |
| 7. Search | 3 | | | | |
| 8. Notifications | 3 | | | | |
| 9. Settings & Preferences | 3 | | | | |
| 10. Real-time Features | 5 | | | | |
| Mobile Tests | 2 | | | | |
| **TOTAL** | **49** | | | | |

### Overall Assessment

| Question | Your Answer |
|----------|-------------|
| **Overall, does the application work as expected?** | ☐ Yes  ☐ No  ☐ Partially |
| **Would you feel comfortable using this application daily?** | ☐ Yes  ☐ No  ☐ Maybe |
| **How would you rate the user experience? (1-5)** | ☐ 1  ☐ 2  ☐ 3  ☐ 4  ☐ 5 |
| **Any features you found confusing?** | |
| **Any features you particularly liked?** | |
| **Any features you wish were added?** | |

### Sign-off

| | |
|---|---|
| **Tester Signature** | _________________________ |
| **Date** | _________________________ |

---

## 6. Issue Reporting Guidelines

If you encounter a problem during testing, please document it using this format:

### Issue Report Template

```
ISSUE #: ___

Test Case ID: (e.g., TC-014)
Test Case Name: (e.g., Send a Text Message)

Issue Summary:
(Brief description of the problem)

Steps to Reproduce:
1.
2.
3.

Expected Result:
(What should have happened)

Actual Result:
(What actually happened)

Screenshot Attached: ☐ Yes  ☐ No

Device/Browser:

Date/Time of Issue:

Additional Notes:
```

### Severity Levels

When reporting issues, classify them by severity:

| Severity | Description | Example |
|----------|-------------|---------|
| **Critical** | Application unusable, data loss | Cannot login, messages not sending |
| **High** | Major feature broken | Cannot create groups, files won't upload |
| **Medium** | Feature works but with problems | Search shows wrong results, slow loading |
| **Low** | Minor issues, cosmetic | Typo in text, icon misaligned |

---

## 7. Glossary

| Term | Definition |
|------|------------|
| **Avatar** | Profile picture or icon representing a user |
| **Conversation** | A chat thread between two or more people |
| **DM (Direct Message)** | Private conversation between two people |
| **Group** | Conversation with 3 or more participants |
| **Mute** | Turn off notifications for a conversation |
| **Poll** | A voting feature to collect opinions |
| **Reaction** | An emoji response to a message (e.g., 👍) |
| **Read Receipt** | Indicator showing a message has been read |
| **Real-time** | Updates happen instantly without refreshing |
| **SSO (Single Sign-On)** | Login once to access multiple applications |
| **Thread** | A reply chain connected to a specific message |
| **UAT** | User Acceptance Testing - testing by end users |

---

## Thank You!

Thank you for participating in the User Acceptance Testing for TMS Chat. Your feedback is valuable in ensuring the application meets your needs and expectations.

If you have any questions during testing, please contact:
- **Email:** _______________
- **Phone:** _______________

---

**Document Version:** 1.0
**Last Updated:** January 2026
**Prepared By:** Development Team
