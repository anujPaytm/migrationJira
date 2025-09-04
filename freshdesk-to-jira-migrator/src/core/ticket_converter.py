"""
Ticket conversion logic for transforming Freshdesk tickets to JIRA issues.
Handles field mapping, description formatting, and custom field assignment.
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import re
from bs4 import BeautifulSoup
from .field_mapper import FieldMapper
from config.mapper_functions import truncate_text, clean_html


class TicketConverter:
    """
    Converts Freshdesk tickets to JIRA issues with proper field mapping.
    """
    
    def __init__(self, field_mapper: FieldMapper):
        """
        Initialize the ticket converter.
        
        Args:
            field_mapper: Field mapper instance
        """
        self.field_mapper = field_mapper
    
    def html_to_clean_text(self, html_content: str) -> str:
        """
        Convert HTML content to plain text while preserving formatting and structure.
        This extracts the actual content from HTML tags, not the tags themselves.
        
        Args:
            html_content: HTML content to convert
            
        Returns:
            Plain text with preserved formatting and structure
        """
        if not html_content or not html_content.strip():
            return ""
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Detect if this is a complex email template vs simple email chain
        is_complex_template = self._is_complex_email_template(soup)
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Handle line breaks
        for br in soup.find_all(['br', 'br/']):
            br.replace_with('\n')
        
        # Handle paragraphs
        for p in soup.find_all('p'):
            if p.get_text().strip():
                p.replace_with(p.get_text().strip() + '\n\n')
            else:
                p.decompose()
        
        # Handle bold text - make it stand out (JIRA uses *text* for bold)
        for tag in soup.find_all(['b', 'strong']):
            text = tag.get_text().strip()
            if text:
                tag.replace_with(f' *{text}* ')
            else:
                tag.decompose()
        
        # Handle italic text (JIRA uses _text_ for italic)
        for tag in soup.find_all(['i', 'em']):
            text = tag.get_text().strip()
            if text:
                tag.replace_with(f' _{text}_ ')
            else:
                tag.decompose()
        
        # Handle links - show text and URL
        for link in soup.find_all('a'):
            href = link.get('href', '')
            text = link.get_text()
            if href and href.startswith('mailto:'):
                # Keep email addresses as they are
                link.replace_with(text)
            elif href:
                # Show text and URL
                link.replace_with(f'{text} ({href})')
            else:
                link.replace_with(text)
        
        # Handle tables - convert to JIRA table format
        # Only process actual table tags, not div structures that look like tables
        for table in soup.find_all('table'):
            # Check if this is a real table with proper structure
            rows = table.find_all('tr')
            if not rows:
                continue
                
            # Verify this table has actual table cells
            has_cells = False
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if cells:
                    has_cells = True
                    break
            
            if not has_cells:
                continue
            
            # Special handling for Google Calendar tables to prevent duplication
            if self._is_google_calendar_table(table):
                # For Google Calendar, extract only the essential meeting information
                table_text = self._extract_google_calendar_table_content(table)
                if table_text:
                    table.replace_with(table_text)
                else:
                    # If no meaningful content, remove the table entirely
                    table.decompose()
                continue
            
            # For complex templates, be more conservative with table conversion
            if is_complex_template:
                # Only convert tables that have clear structure (not layout tables)
                if len(rows) <= 10 and all(len(row.find_all(['td', 'th'])) <= 5 for row in rows):
                    table_text = '\n'
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if cells:
                            # Add header formatting with JIRA table syntax
                            if row.find('th'):
                                row_text = '||' + '||'.join([f'*{cell.get_text().strip()}*' for cell in cells]) + '||'
                            else:
                                row_text = '||' + '||'.join([cell.get_text().strip() for cell in cells]) + '||'
                            table_text += row_text + '\n'
                    table_text += '\n'
                    table.replace_with(table_text)
                else:
                    # For complex layout tables, just extract text without table formatting
                    table_text = '\n' + table.get_text(separator='\n', strip=True) + '\n\n'
                    table.replace_with(table_text)
            else:
                # For simple email chains, convert all tables normally
                table_text = '\n'
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if cells:
                        # Add header formatting with JIRA table syntax
                        if row.find('th'):
                            row_text = '||' + '||'.join([f'*{cell.get_text().strip()}*' for cell in cells]) + '||'
                        else:
                            row_text = '||' + '||'.join([cell.get_text().strip() for cell in cells]) + '||'
                        table_text += row_text + '\n'
                table_text += '\n'
                table.replace_with(table_text)
        
        # Handle images - show descriptive text
        for img in soup.find_all('img'):
            src = img.get('src', '')
            alt = img.get('alt', 'Image')
            if src:
                img.replace_with(f'[Image: {alt}] - URL: {src}')
            else:
                img.replace_with(f'[Image: {alt}]')
        
        # Handle lists
        for ul in soup.find_all('ul'):
            list_text = '\n'
            for li in ul.find_all('li'):
                list_text += f'• {li.get_text().strip()}\n'
            list_text += '\n'
            ul.replace_with(list_text)
        
        for ol in soup.find_all('ol'):
            list_text = '\n'
            for i, li in enumerate(ol.find_all('li'), 1):
                list_text += f'{i}. {li.get_text().strip()}\n'
            list_text += '\n'
            ol.replace_with(list_text)
        
        # Handle headers
        for i in range(1, 7):
            for h in soup.find_all(f'h{i}'):
                prefix = '#' * i + ' '
                h.replace_with(f'{prefix}{h.get_text().strip()}\n\n')
        
        # Handle blockquotes (email quotes) - convert > to proper quote format
        for blockquote in soup.find_all('blockquote'):
            lines = blockquote.get_text().strip().split('\n')
            quoted_text = '\n'.join([f'> {line}' for line in lines if line.strip()])
            blockquote.replace_with(f'\n{quoted_text}\n\n')
        
        # Handle code blocks
        for pre in soup.find_all('pre'):
            code_text = pre.get_text().strip()
            pre.replace_with(f'\n```\n{code_text}\n```\n\n')
        
        # Handle inline code
        for code in soup.find_all('code'):
            code_text = code.get_text().strip()
            code.replace_with(f'`{code_text}`')
        
        # Also handle any remaining > symbols that might be from email quotes
        # Replace standalone > symbols with proper quote format
        text = soup.get_text()
        
        # Clean up extra whitespace and newlines
        text = re.sub(r'\n\s*\n', '\n\n', text)  # Remove multiple empty lines
        text = re.sub(r'[ \t]+', ' ', text)  # Normalize spaces
        text = re.sub(r'\n{3,}', '\n\n', text)  # Limit consecutive newlines to 2
        
        # Handle email quote symbols that might interfere with JIRA formatting
        # Simply remove problematic > symbols that break formatting
        text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)  # Remove > at start of lines
        text = re.sub(r'\n>\s*', '\n', text)  # Remove > after newlines
        text = re.sub(r'\s*>\s*', ' ', text)  # Remove standalone > symbols with spaces
        
        # Fix email headers formatting - put each header on its own line
        # Handle bold email headers first - use exact pattern matching
        # Only process if we're in an email context (not in complex HTML templates)
        if not is_complex_template and ('From:' in text or 'To:' in text or 'Subject:' in text):
            text = re.sub(r'(\s+)\*From:\*(\s+)', r'\n\n*From:* ', text)
            text = re.sub(r'(\s+)\*To:\*(\s+)', r'\n\n*To:* ', text)
            text = re.sub(r'(\s+)\*Cc:\*(\s+)', r'\n\n*Cc:* ', text)
            text = re.sub(r'(\s+)\*Bcc:\*(\s+)', r'\n\n*Bcc:* ', text)
            text = re.sub(r'(\s+)\*Subject:\*(\s+)', r'\n\n*Subject:* ', text)
            text = re.sub(r'(\s+)\*Sent:\*(\s+)', r'\n\n*Sent:* ', text)
            text = re.sub(r'(\s+)\*Date:\*(\s+)', r'\n\n*Date:* ', text)
            
            # Handle regular email headers
            text = re.sub(r'(\s+)From:(\s+)', r'\n\nFrom: ', text)
            text = re.sub(r'(\s+)To:(\s+)', r'\n\nTo: ', text)
            text = re.sub(r'(\s+)Cc:(\s+)', r'\n\nCc: ', text)
            text = re.sub(r'(\s+)Bcc:(\s+)', r'\n\nBcc: ', text)
            text = re.sub(r'(\s+)Subject:(\s+)', r'\n\nSubject: ', text)
            text = re.sub(r'(\s+)Sent:(\s+)', r'\n\nSent: ', text)
            text = re.sub(r'(\s+)Date:(\s+)', r'\n\nDate: ', text)
        
        # Add single line separators between different email conversations
        # Look for patterns that indicate new email threads
        # Only process if we're in an email context and not a complex template
        if not is_complex_template and 'From:' in text:
            text = re.sub(r'\n\s*\*From:\*', '\n\n---\n\n*From:*', text)
            text = re.sub(r'\n\s*From:', '\n\n---\n\nFrom:', text)
        
        # Clean up multiple consecutive separators
        text = re.sub(r'--- NEW EMAIL ---\s*\n\s*--- NEW EMAIL ---', '--- NEW EMAIL ---', text)
        
        # Ensure proper spacing around email content
        text = re.sub(r'\n{3,}', '\n\n', text)  # Limit consecutive newlines to 2
        
        text = text.strip()
        
        return text
    
    def html_to_clean_text_improved(self, html_content: str) -> str:
        """
        Convert HTML content to clean, readable plain text using html2text.
        Handles both complex and simple HTML files with outer table detection.
        Outputs plain text that JIRA won't auto-format.
        
        Args:
            html_content: HTML content to convert
            
        Returns:
            Clean, readable plain text
        """
        if not html_content or not html_content.strip():
            return ""
        
        # Log the input size for debugging
        input_size = len(html_content)
        print(f"🔄 Processing HTML content: {input_size} characters")
        
        try:
            # Import html2text here to avoid dependency issues
            import html2text
            
            # Step 1: Clean HTML and handle outer tables
            print("📝 Step 1: Cleaning HTML and handling outer tables...")
            cleaned_html = self._clean_html_for_conversion(html_content)
            cleaned_size = len(cleaned_html)
            print(f"📝 Cleaned HTML size: {cleaned_size} characters")
            
            # Step 2: Convert HTML to markdown using html2text
            print("📝 Step 2: Converting HTML to markdown...")
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.ignore_emphasis = False
            h.ignore_tables = False
            h.body_width = 0  # No line wrapping
            
            markdown_text = h.handle(cleaned_html)
            markdown_size = len(markdown_text)
            print(f"📝 Markdown size: {markdown_size} characters")
            
            # Step 3: Convert markdown to clean, readable plain text
            print("📝 Step 3: Converting markdown to clean text...")
            clean_text = self._convert_markdown_to_clean_text(markdown_text)
            final_size = len(clean_text)
            print(f"📝 Final clean text size: {final_size} characters")
            
            # Check for significant data loss
            if final_size < input_size * 0.5:  # If we lost more than 50% of content
                print(f"⚠️ WARNING: Significant data loss detected!")
                print(f"   Input: {input_size} chars")
                print(f"   Output: {final_size} chars")
                print(f"   Loss: {input_size - final_size} chars ({((input_size - final_size) / input_size * 100):.1f}%)")
                
                # Fallback to original method for safety
                print("🔄 Falling back to original conversion method...")
                fallback_text = self.html_to_clean_text(html_content)
                fallback_size = len(fallback_text)
                print(f"📝 Fallback method size: {fallback_size} characters")
                
                # Use whichever method preserved more content
                if fallback_size > final_size:
                    print("✅ Using fallback method (preserved more content)")
                    return fallback_text
                else:
                    print("✅ Using improved method (despite data loss)")
            
            # Additional content loss detection
            if self._detect_content_loss(html_content, clean_text):
                print("🔄 Content loss detected, falling back to original method...")
                fallback_text = self.html_to_clean_text(html_content)
                print("✅ Using fallback method to preserve content")
                return fallback_text
            
            # Final safety check - ensure we have meaningful content
            if len(clean_text.strip()) < 100:  # If output is too short
                print("⚠️ Output too short, falling back to original method...")
                fallback_text = self.html_to_clean_text(html_content)
                print("✅ Using fallback method for safety")
                return fallback_text
            
            return clean_text
            
        except ImportError:
            # Fallback to original method if html2text is not available
            print("⚠️ html2text not available, falling back to original conversion method")
            return self.html_to_clean_text(html_content)
        except Exception as e:
            print(f"⚠️ Error in improved conversion: {str(e)}")
            print("🔄 Falling back to original conversion method...")
            return self.html_to_clean_text(html_content)
    
    def _clean_html_for_conversion(self, html_content: str) -> str:
        """
        Pre-processes HTML to handle outer tables and clean up content.
        Detects if there's an outer wrapper table and extracts the inner content.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Special handling for Google Calendar HTML
        if self._is_google_calendar_html(soup):
            return self._clean_google_calendar_html(soup)
        
        # Check if there's an outer wrapper table (common in email HTML)
        outer_table = soup.find('table')
        if outer_table:
            # Look for inner content - check if outer table contains another table
            inner_tables = outer_table.find_all('table')
            if len(inner_tables) > 1:
                # Multiple tables found - extract content from the most relevant one
                # Usually the content table is the one with more complex structure
                content_table = None
                max_cells = 0
                
                for table in inner_tables:
                    cells = len(table.find_all(['td', 'th']))
                    if cells > max_cells:
                        max_cells = cells
                        content_table = table
                
                if content_table:
                    # Extract content from the most relevant table
                    return str(content_table)
                else:
                    # If no clear content table, extract all inner content
                    inner_content = outer_table.find_all(['div', 'p', 'span', 'table'])
                    if inner_content:
                        return '\n'.join([str(item) for item in inner_content])
                    else:
                        # Fallback: get text content
                        return outer_table.get_text(separator='\n', strip=True)
            elif len(inner_tables) == 1:
                # Single inner table - extract it
                return str(inner_tables[0])
            else:
                # No inner tables, extract content from outer table
                return outer_table.get_text(separator='\n', strip=True)
        
        # No outer table found, return original HTML
        return html_content
    
    def _is_google_calendar_html(self, soup) -> bool:
        """
        Detects if the HTML is from Google Calendar based on specific markers.
        """
        # Check for Google Calendar specific elements
        google_calendar_indicators = [
            'Google Calendar',
            'calendar.google.com',
            'meet.google.com',
            'Process of billing Discussion',  # Common in meeting invites
            'Join with Google Meet',
            'View map'
        ]
        
        text_content = soup.get_text().lower()
        return any(indicator.lower() in text_content for indicator in google_calendar_indicators)
    
    def _clean_google_calendar_html(self, soup) -> str:
        """
        Specialized cleaning for Google Calendar HTML to prevent table duplication.
        Extracts meaningful content while preserving structure.
        """
        # Remove hidden elements and unnecessary styling
        for element in soup.find_all(['span', 'div'], style=True):
            if 'display:none' in element.get('style', '') or 'display: none' in element.get('style', ''):
                element.decompose()
        
        # For Google Calendar, we want to extract the main meeting information
        # without the complex table structure that causes duplication
        
        # Look for key meeting information elements
        meeting_info = []
        
        # Extract meeting title/description
        title_elements = soup.find_all(['h1', 'h2', 'h3', 'div'], class_=lambda x: x and 'primary-text' in x)
        for element in title_elements:
            text = element.get_text(strip=True)
            if text and len(text) > 10:
                meeting_info.append(text)
        
        # Extract meeting time
        time_elements = soup.find_all(['time', 'span'], datetime=True)
        for element in time_elements:
            text = element.get_text(strip=True)
            if text and len(text) > 5:
                meeting_info.append(text)
        
        # Extract location
        location_elements = soup.find_all(['div', 'span'], string=lambda x: x and 'Location' in x)
        for element in location_elements:
            # Get the next sibling or parent that contains the actual location
            location_text = self._extract_location_text(element)
            if location_text:
                meeting_info.append(f"Location: {location_text}")
        
        # Extract meeting link
        meet_links = soup.find_all('a', href=lambda x: x and 'meet.google.com' in x)
        if meet_links:
            meet_link = meet_links[0].get('href')
            meeting_info.append(f"Meeting Link: {meet_link}")
        
        # Extract phone information
        phone_elements = soup.find_all(['div', 'span'], string=lambda x: x and 'Join by phone' in x)
        for element in phone_elements:
            phone_text = self._extract_phone_text(element)
            if phone_text:
                meeting_info.append(f"Phone: {phone_text}")
        
        # Extract guests
        guest_elements = soup.find_all(['div', 'span'], string=lambda x: x and 'Guests' in x)
        for element in guest_elements:
            guest_text = self._extract_guest_text(element)
            if guest_text:
                meeting_info.append(f"Guests: {guest_text}")
        
        # If we found structured meeting info, use it
        if meeting_info:
            return '\n\n'.join(meeting_info)
        
        # Fallback: extract text content more carefully
        return self._extract_clean_text_content(soup)
    
    def _extract_location_text(self, location_element):
        """Extract location text from location element."""
        # Look for location text in nearby elements
        parent = location_element.parent
        if parent:
            # Find the next element that contains address-like text
            for sibling in parent.find_next_siblings():
                text = sibling.get_text(strip=True)
                if text and len(text) > 20 and ',' in text:
                    return text
        return None
    
    def _extract_phone_text(self, phone_element):
        """Extract phone information from phone element."""
        # Look for phone number in nearby elements
        parent = phone_element.parent
        if parent:
            # Find phone number and PIN
            phone_text = parent.get_text(strip=True)
            if phone_text:
                # Clean up the phone text
                lines = phone_text.split('\n')
                phone_info = []
                for line in lines:
                    line = line.strip()
                    if line and ('+' in line or 'PIN:' in line):
                        phone_info.append(line)
                if phone_info:
                    return ' '.join(phone_info)
        return None
    
    def _extract_guest_text(self, guest_element):
        """Extract guest information from guest element."""
        # Look for guest emails in nearby elements
        parent = guest_element.parent
        if parent:
            # Find guest emails
            guest_emails = parent.find_all('a', href=lambda x: x and 'mailto:' in x)
            if guest_emails:
                emails = [email.get('href').replace('mailto:', '') for email in guest_emails]
                return ', '.join(emails)
        return None
    
    def _extract_clean_text_content(self, soup):
        """Extract clean text content without table duplication."""
        # Remove all table elements to prevent duplication
        for table in soup.find_all('table'):
            table.decompose()
        
        # Extract text from remaining elements
        text_elements = []
        for element in soup.find_all(['div', 'p', 'span']):
            text = element.get_text(strip=True)
            if text and len(text) > 5:
                text_elements.append(text)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_text = []
        for text in text_elements:
            if text not in seen:
                seen.add(text)
                unique_text.append(text)
        
        return '\n\n'.join(unique_text)
    
    def _extract_table_text(self, table_element) -> str:
        """
        Extracts readable text from table elements without duplication.
        """
        rows = []
        for row in table_element.find_all('tr'):
            cells = []
            for cell in row.find_all(['td', 'th']):
                cell_text = cell.get_text(strip=True)
                if cell_text:
                    cells.append(cell_text)
            if cells:
                rows.append(' | '.join(cells))
        
        if rows:
            return '\n'.join(rows)
        return ''
    
    def _convert_markdown_to_clean_text(self, markdown_text: str) -> str:
        """
        Converts markdown text to clean, readable plain text.
        Removes markdown syntax but preserves structure and readability.
        """
        import re
        
        # Split into lines for processing
        lines = markdown_text.split('\n')
        clean_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Handle headers - convert to plain text with clear separation
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                text = line.lstrip('#').strip()
                if level <= 3:  # Only process h1, h2, h3
                    clean_lines.append('')  # Add space before header
                    clean_lines.append(text.upper())  # Make headers stand out
                    clean_lines.append('')  # Add space after header
                else:
                    clean_lines.append(text)
            
            # Handle tables - convert to readable format
            elif line.startswith('|'):
                # Check if this is a table header separator
                if '---' in line:
                    # Skip separator lines
                    i += 1
                    continue
                
                # Process table row
                cells = [cell.strip() for cell in line.split('|') if cell.strip()]
                if cells:
                    # Format as readable text
                    if i == 0 or (i > 0 and '---' in lines[i-1]):
                        # This is a header row - make it stand out
                        clean_lines.append('  '.join(cells))
                        clean_lines.append('  '.join(['-' * len(cell) for cell in cells]))
                    else:
                        # This is a data row
                        clean_lines.append('  '.join(cells))
            
            # Handle lists - convert to plain text with clear structure
            elif line.startswith('* ') or line.startswith('- '):
                clean_lines.append(f"• {line[2:].strip()}")
            elif line.startswith('1. '):
                clean_lines.append(f"1. {line[3:].strip()}")
            
            # Handle nested lists
            elif line.startswith('  * ') or line.startswith('  - '):
                clean_lines.append(f"  • {line[4:].strip()}")
            elif line.startswith('    1. '):
                clean_lines.append(f"  1. {line[6:].strip()}")
            
            # Handle bold and italic - remove markdown but preserve emphasis
            elif '**' in line or '__' in line:
                # Remove markdown but keep text
                processed_line = line
                processed_line = re.sub(r'\*\*(.*?)\*\*', r'\1', processed_line)
                processed_line = re.sub(r'__(.*?)__', r'\1', processed_line)
                clean_lines.append(processed_line)
            
            # Handle links - convert to readable format
            elif '[' in line and '](' in line:
                # Convert markdown links to readable format: [text](url) -> text (url)
                processed_line = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', line)
                clean_lines.append(processed_line)
            
            # Handle code blocks - convert to readable format
            elif line.startswith('```'):
                # Start/end of code block
                if line == '```':
                    clean_lines.append('')
                    clean_lines.append('--- CODE BLOCK ---')
                    clean_lines.append('')
                else:
                    # Code block with language specification
                    lang = line[3:].strip()
                    clean_lines.append('')
                    clean_lines.append(f'--- {lang.upper()} CODE ---')
                    clean_lines.append('')
            
            # Handle inline code - convert to readable format
            elif '`' in line:
                # Convert inline code: `code` -> [code]
                processed_line = re.sub(r'`([^`]+)`', r'[\1]', line)
                clean_lines.append(processed_line)
            
            # Handle horizontal rules
            elif line.startswith('---') or line.startswith('***'):
                clean_lines.append('')
                clean_lines.append('─' * 50)  # Use Unicode line
                clean_lines.append('')
            
            # Handle blockquotes - convert to readable format
            elif line.startswith('> '):
                clean_lines.append(f"Quote: {line[2:].strip()}")
            
            # Handle regular text
            elif line:
                clean_lines.append(line)
            
            # Handle empty lines
            else:
                clean_lines.append('')
            
            i += 1
        
        # Clean up multiple empty lines
        result = []
        prev_empty = False
        for line in clean_lines:
            if line == '':
                if not prev_empty:
                    result.append(line)
                    prev_empty = True
            else:
                result.append(line)
                prev_empty = False
        
        return '\n'.join(result)
    
    def _is_complex_email_template(self, soup) -> bool:
        """
        Detect if the HTML is a complex email template vs a simple email chain.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            True if complex template, False if simple email chain
        """
        # Check for complex email template indicators
        has_webkit = soup.find(class_='webkit') is not None
        has_complex_tables = len(soup.find_all('table')) > 5  # More than 5 tables suggests template
        has_nested_divs = len(soup.find_all('div')) > 100  # Many divs suggest complex layout
        
        # Check for email template specific classes
        has_template_classes = any(
            soup.find(class_=cls) for cls in ['outer', 'inner', 'contents', 'one-column']
        )
        
        # Check for MSO (Microsoft Outlook) specific tags
        has_mso_tags = len(soup.find_all(class_=lambda x: x and 'Mso' in x)) > 0
        
        # If it has multiple indicators of complexity, treat as template
        complexity_score = sum([
            has_webkit,
            has_complex_tables,
            has_nested_divs,
            has_template_classes,
            has_mso_tags
        ])
        
        return complexity_score >= 2  # At least 2 complexity indicators
    
    def html_to_markdown(self, html_content: str) -> str:
        """
        Convert HTML content to JIRA Wiki markup for best formatting.
        This method preserves the structure and formatting of the original HTML.
        """
        if not html_content:
            return ""
        
        from bs4 import BeautifulSoup
        
        def clean_email_html(html: str) -> str:
            """
            Pre-process HTML to extract actual content from email wrapper tables
            """
            soup = BeautifulSoup(html, "html.parser")
            
            # Remove script and style tags
            for tag in soup(["script", "style"]):
                tag.decompose()
            
            # Remove invisible spacer elements
            for tag in soup.find_all(["div", "span"]):
                if tag.get("style") and "font-size:0px" in tag.get("style"):
                    tag.decompose()
            
            # Look for the main content table and preserve it
            main_content_table = soup.find("table", style=lambda x: x and "border:1px solid #d0d0d0" in x)
            
            if main_content_table:
                # Create a new clean structure
                new_soup = BeautifulSoup("<html><body></body></html>", "html.parser")
                body = new_soup.body
                
                # Add the main content table
                body.append(main_content_table)
                
                # Look for other content outside the main table
                for tag in soup.find_all(["p", "div", "span"]):
                    if tag.get("style") and "font-size:14px" in tag.get("style"):
                        # This looks like actual content
                        body.append(tag)
                
                return str(new_soup)
            
            return str(soup)
        
        def html_to_jira_wiki(html: str) -> str:
            """
            Convert HTML to JIRA Wiki markup with proper table handling
            """
            soup = BeautifulSoup(html, "html.parser")
            
            # Handle tables - convert to proper JIRA Wiki format
            for table in soup.find_all("table"):
                rows = []
                for tr in table.find_all("tr"):
                    cells = []
                    for th in tr.find_all("th"):
                        cells.append(th.get_text(strip=True))
                    for td in tr.find_all("td"):
                        cells.append(td.get_text(strip=True))
                    
                    # Build JIRA Wiki row
                    if cells:
                        if not rows:  # First row = header
                            rows.append("|| " + " || ".join(cells) + " ||")
                        else:
                            rows.append("| " + " | ".join(cells) + " |")
                
                # Replace table with JIRA Wiki markup
                table.replace_with("\n".join(rows))
            
            # Handle other formatting
            for tag in soup.find_all(["b", "strong"]):
                tag.string = f"*{tag.get_text(strip=True)}*"
            
            for tag in soup.find_all(["i", "em"]):
                tag.string = f"_{tag.get_text(strip=True)}_"
            
            for tag in soup.find_all("a", href=True):
                text = tag.get_text(strip=True)
                href = tag["href"]
                tag.string = f"[{text}|{href}]"
            
            # Convert line breaks
            for br in soup.find_all("br"):
                br.replace_with("\n")
            
            # Get clean text
            text = soup.get_text("\n", strip=True)
            
            # Clean up excessive newlines
            import re
            text = re.sub(r"\n{3,}", "\n\n", text)
            
            # Add breaklines between different emails for better readability
            # Look for email header patterns and add separators
            if 'From:' in text or 'To:' in text or 'Subject:' in text:
                # Add separators only before From: headers (indicating new emails)
                # Skip the first From: header to avoid separator at the beginning
                text = re.sub(r'\n\s*From:', '\n\n---\n\nFrom:', text)
                text = re.sub(r'\n\s*\*From:\*', '\n\n---\n\n*From:*', text)
                
                # Clean up multiple consecutive separators
                text = re.sub(r'---\s*\n\s*---', '---', text)
                text = re.sub(r'\n{3,}', '\n\n', text)  # Limit consecutive newlines to 2
            
            return text
        
        # First clean the HTML, then convert to JIRA Wiki markup
        cleaned_html = clean_email_html(html_content)
        return html_to_jira_wiki(cleaned_html)
    
    def convert_to_jira_issue(self, 
                             ticket: Dict[str, Any],
                             conversations: List[Dict[str, Any]] = None,
                             ticket_attachments: List[Dict[str, Any]] = None,
                             conversation_attachments: List[Dict[str, Any]] = None,
                             user_data: Dict[str, Any] = None,
                             use_raw_html: bool = False,
                             use_jira_wiki: bool = False) -> Dict[str, Any]:
        """
        Convert a Freshdesk ticket to JIRA issue format.
        
        Args:
            ticket: Freshdesk ticket data
            conversations: List of conversation data
            ticket_attachments: List of ticket attachment data
            conversation_attachments: List of conversation attachment data
            user_data: User information data
            
        Returns:
            JIRA issue dictionary
        """
        # Initialize JIRA issue structure
        jira_issue = {
            "fields": {
                "project": {"key": "FTJM"},  # Default project key
                "issuetype": {"name": "Task"}  # Default issue type
            }
        }
        
        # Map ticket fields using regular approach (not hierarchical for ticket fields)
        mapped_fields, unmapped_ticket_fields = self.field_mapper.map_ticket_fields(ticket, user_data)
        
        # Add mapped fields to JIRA issue
        for field_name, field_value in mapped_fields.items():
            jira_issue["fields"][field_name] = field_value
        
        # Ensure summary field is always set
        if not jira_issue["fields"].get('summary') or jira_issue["fields"]['summary'].strip() == '':
            ticket_id = ticket.get('id', 'Unknown')
            jira_issue["fields"]['summary'] = f"Freshdesk Ticket #{ticket_id}: No Subject Provided"
        
        # Build description using hierarchical approach
        description_parts = []
        
        # Add original description if available (convert HTML to clean plain text, markdown, or use raw HTML)
        description_html = ticket.get('description', '')
        if description_html:
            if use_jira_wiki:
                # Convert HTML to Markdown for best formatting
                markdown_description = self.html_to_markdown(description_html)
                description_parts.append(f"**— Description —**\n{markdown_description}")
            elif use_raw_html:
                # Use raw HTML directly for JIRA rendering
                description_parts.append(f"**— Description —**\n{description_html}")
            else:
                # Convert HTML to clean, readable plain text with proper formatting
                plain_text_description = self.html_to_clean_text_improved(description_html)
                description_parts.append(f"**— Description —**\n{plain_text_description}")
        
        # Add unmapped ticket fields to description (only if not mapped to custom fields)
        # Exclude HTML fields and description_text to avoid duplication
        if unmapped_ticket_fields:
            metadata_lines = ["**— Freshdesk Ticket Metadata —**"]
            for field_name, field_value in unmapped_ticket_fields.items():
                # Skip HTML description fields and description_text to avoid duplication
                if field_name in ['description', 'structured_description', 'description_text']:
                    continue
                    
                if field_value is not None and field_value != "":
                    if isinstance(field_value, list):
                        field_value = ', '.join(str(v) for v in field_value)
                    metadata_lines.append(f"{field_name}: {field_value}")
            
            # Only add metadata section if there are actual fields to show
            if len(metadata_lines) > 1:
                description_parts.append('\n'.join(metadata_lines))
        
        # Map conversations using hierarchical approach
        conv_mapped_fields = {}
        conv_unmapped_fields = {}
        
        if conversations:
            conv_mapped_fields, conv_unmapped_fields = self.field_mapper.map_hierarchical_fields(conversations, "conversation_fields", user_data)
            
            # Add all mapped fields (overflow is handled by field mapper)
            for field_name, field_value in conv_mapped_fields.items():
                jira_issue["fields"][field_name] = field_value
        
        # Add unmapped conversations to description (only if parent field is not mapped)
        if conv_unmapped_fields and not conv_mapped_fields:
            formatted_conversations = self._format_conversations_colon_separated(conversations, user_data)
            if formatted_conversations:
                description_parts.append(formatted_conversations)
        
        # Map attachments using hierarchical approach
        all_attachments = ticket_attachments + conversation_attachments if ticket_attachments and conversation_attachments else (ticket_attachments or conversation_attachments or [])
        att_mapped_fields = {}
        att_unmapped_fields = {}
        
        if all_attachments:
            att_mapped_fields, att_unmapped_fields = self.field_mapper.map_hierarchical_fields(all_attachments, "attachment_fields", user_data)
            
            # Add all mapped fields (overflow is handled by field mapper)
            for field_name, field_value in att_mapped_fields.items():
                jira_issue["fields"][field_name] = field_value
        
        # Add unmapped attachments to description (only if parent field is not mapped)
        if att_unmapped_fields and not att_mapped_fields:
            formatted_attachments = self._format_attachments_colon_separated(all_attachments, user_data)
            if formatted_attachments:
                description_parts.append(formatted_attachments)
        
        # Combine all description parts with overflow handling
        if description_parts:
            # Check total length before joining to avoid expensive operations
            total_length = sum(len(part) for part in description_parts) + (len(description_parts) - 1) * 2  # Account for '\n\n' separators
            max_description_length = 32000  # Leave some buffer
            
            if total_length > max_description_length:
                print(f"Warning: Description too long ({total_length} chars), using overflow fields")
                
                # Use field mapper's overflow handling instead of hardcoded fields
                full_description = '\n\n'.join(description_parts)
                overflow_mappings = self.field_mapper.handle_description_overflow(full_description, max_description_length)
                
                # Add overflow fields to the JIRA issue
                for field_name, field_value in overflow_mappings.items():
                    jira_issue["fields"][field_name] = field_value
                
                # Set the main description to the first chunk
                jira_issue["fields"]["description"] = overflow_mappings.get("description", "")
            else:
                full_description = '\n\n'.join(description_parts)
                jira_issue["fields"]["description"] = full_description
        
        # Don't add user information to avoid description length issues
        # User mapping is already handled in the field mapping above
        
        return jira_issue
    
    def _format_description_section(self, title: str, content: str) -> str:
        """
        Format a description section with title and content.
        
        Args:
            title: Section title
            content: Section content
            
        Returns:
            Formatted section text
        """
        if not content:
            return ""
        
        # Clean HTML if present
        clean_content = clean_html(content)
        
        return f"**{title}:**\n{clean_content}"
    
    def _format_conversations(self, conversations: List[Dict[str, Any]]) -> str:
        """
        Format conversations for description.
        
        Args:
            conversations: List of conversation data
            
        Returns:
            Formatted conversations text
        """
        if not conversations:
            return ""
        
        lines = ["**Conversations:**"]
        
        for i, conversation in enumerate(conversations, 1):
            lines.append(f"\n**Conversation {i}:**")
            
            # Map conversation fields
            mapped_fields, unmapped_fields = self.field_mapper.map_conversation_fields(conversation)
            
            # Add mapped fields
            for field_name, field_value in mapped_fields.items():
                if field_value is not None and field_value != "":
                    lines.append(f"**{field_name}:** {field_value}")
            
            # Add unmapped fields
            for field_name, field_value in unmapped_fields.items():
                if field_value is not None and field_value != "":
                    if isinstance(field_value, (list, dict)):
                        formatted_value = json.dumps(field_value, indent=2)
                    else:
                        formatted_value = str(field_value)
                    lines.append(f"**{field_name}:** {formatted_value}")
        
        return "\n".join(lines)
    
    def _format_attachments(self, attachments: List[Dict[str, Any]], title: str) -> str:
        """
        Format attachments for description.
        
        Args:
            attachments: List of attachment data
            title: Section title
            
        Returns:
            Formatted attachments text
        """
        if not attachments:
            return ""
        
        lines = [f"**{title}:**"]
        
        for i, attachment in enumerate(attachments, 1):
            lines.append(f"\n**Attachment {i}:**")
            
            # Map attachment fields
            mapped_fields, unmapped_fields = self.field_mapper.map_attachment_fields(attachment)
            
            # Add mapped fields
            for field_name, field_value in mapped_fields.items():
                if field_value is not None and field_value != "":
                    lines.append(f"**{field_name}:** {field_value}")
            
            # Add unmapped fields
            for field_name, field_value in unmapped_fields.items():
                if field_value is not None and field_value != "":
                    if isinstance(field_value, (list, dict)):
                        formatted_value = json.dumps(field_value, indent=2)
                    else:
                        formatted_value = str(field_value)
                    lines.append(f"**{field_name}:** {formatted_value}")
        
        return "\n".join(lines)
    
    def set_project_key(self, jira_issue: Dict[str, Any], project_key: str):
        """
        Set the project key for a JIRA issue.
        
        Args:
            jira_issue: JIRA issue dictionary
            project_key: Project key
        """
        jira_issue["fields"]["project"]["key"] = project_key
    
    def set_issue_type(self, jira_issue: Dict[str, Any], issue_type: str):
        """
        Set the issue type for a JIRA issue.
        
        Args:
            jira_issue: JIRA issue dictionary
            issue_type: Issue type name or ID
        """
        # Check if issue_type is a numeric ID
        if issue_type.isdigit():
            jira_issue["fields"]["issuetype"]["id"] = issue_type
        else:
            jira_issue["fields"]["issuetype"]["name"] = issue_type
    
    def add_custom_field(self, jira_issue: Dict[str, Any], field_name: str, field_value: Any):
        """
        Add a custom field to the JIRA issue.
        
        Args:
            jira_issue: JIRA issue dictionary
            field_name: Custom field name
            field_value: Field value
        """
        jira_issue["fields"][field_name] = field_value
    
    def get_mapped_fields_summary(self, ticket: Dict[str, Any], user_data: dict = None) -> Dict[str, Any]:
        """
        Get a summary of mapped and unmapped fields for a ticket.
        
        Args:
            ticket: Freshdesk ticket data
            user_data: User data for context
            
        Returns:
            Summary dictionary
        """
        mapped_fields, unmapped_fields = self.field_mapper.map_ticket_fields(ticket, user_data)
        
        return {
            "mapped_fields": list(mapped_fields.keys()),
            "unmapped_fields": list(unmapped_fields.keys()),
            "total_fields": len(ticket),
            "mapping_coverage": len(mapped_fields) / len(ticket) if ticket else 0
        }
    
    def _format_conversations_colon_separated(self, conversations: List[Dict[str, Any]], user_data: dict = None) -> str:
        """
        Format conversations in pipe-separated format (regardless of where they're stored).
        
        Args:
            conversations: List of conversation data
            user_data: User data for context
            
        Returns:
            Formatted conversations text
        """
        if not conversations:
            return ""
        
        # Define headers once - reordered with time fields first, then id
        headers = ["created_at", "updated_at", "conversation_id", "user_id", "private", "to_email", "from_email", "cc_email", "bcc_email"]
        
        # Create JIRA Wiki table header
        conversations_lines = ["**— Conversations —**"]
        conversations_lines.append("|| " + " || ".join(headers) + " ||")
        
        for conv in conversations:
            # Get user information from user_data
            user_email = 'NA'
            if user_data and conv.get('user_id'):
                user_id = str(conv.get('user_id'))
                # Search in agents first
                agents = user_data.get('agents', {})
                if user_id in agents:
                    agent = agents[user_id]
                    if 'contact' in agent and agent['contact'].get('email'):
                        user_email = agent['contact']['email']
                else:
                    # Search in contacts
                    contacts = user_data.get('contacts', {})
                    if user_id in contacts:
                        contact = contacts[user_id]
                        if contact.get('email'):
                            user_email = contact['email']
            
            # Format dates
            created_at = conv.get('created_at', 'N/A')
            updated_at = conv.get('updated_at', 'N/A')
            
            # Format privacy status
            is_private = conv.get('private', False)
            privacy_status = "private" if is_private else "public"
            
            # Get email fields
            to_emails = ', '.join(conv.get('to_emails', []))
            from_email = conv.get('from_email', 'N/A')
            cc_emails = ', '.join(conv.get('cc_emails', []))
            bcc_emails = ', '.join(conv.get('bcc_emails', []))
            
            # Get values - reordered to match headers
            values = [
                str(created_at),
                str(updated_at),
                str(conv.get('id', 'N/A')),
                str(user_email),
                str(privacy_status),
                str(to_emails),
                str(from_email),
                str(cc_emails),
                str(bcc_emails)
            ]
            
            # Only use body_text, never body (HTML)
            body_text = conv.get('body_text', '')
            
            # Add table row
            conversations_lines.append("| " + " | ".join(values) + " |")
            
            # Add body_text on next line for better readability
            if body_text.strip():
                conversations_lines.extend([
                    "",  # Add blank line before body text
                    body_text,
                    "---",
                    ""  # Add extra blank line for better readability
                ])
        
        return '\n'.join(conversations_lines)
    
    def _format_attachments_colon_separated(self, attachments: List[Dict[str, Any]], user_data: dict = None) -> str:
        """
        Format attachments in pipe-separated format (regardless of where they're stored).
        
        Args:
            attachments: List of attachment data
            user_data: User data for context
            
        Returns:
            Formatted attachments text
        """
        if not attachments:
            return ""
        
        # Define headers once - reordered with time fields first, then id
        headers = ["created_at", "updated_at", "attachment_id", "file name", "size", "user_id", "conversation_id"]
        
        # Create JIRA Wiki table header
        attachment_lines = ["**— Attachment Details —**"]
        attachment_lines.append("|| " + " || ".join(headers) + " ||")
        
        for attachment in attachments:
            # Get user information from user_data
            user_email = 'NA'
            if user_data and attachment.get('user_id'):
                user_id = str(attachment.get('user_id'))
                # Search in agents first
                agents = user_data.get('agents', {})
                if user_id in agents:
                    agent = agents[user_id]
                    if 'contact' in agent and agent['contact'].get('email'):
                        user_email = agent['contact']['email']
                else:
                    # Search in contacts
                    contacts = user_data.get('contacts', {})
                    if user_id in contacts:
                        contact = contacts[user_id]
                        if contact.get('email'):
                            user_email = contact['email']
            
            # Format attachment info
            attachment_id = attachment.get('id', 'N/A')
            original_name = attachment.get('name', 'N/A')
            new_name = f"{attachment_id}_{original_name}"  # attachmentId_nameofthefile
            
            # Get values - reordered to match headers
            values = [
                str(attachment.get('created_at', 'N/A')),
                str(attachment.get('updated_at', 'N/A')),
                str(attachment_id),
                str(new_name),
                str(attachment.get('size', 'N/A')),
                str(user_email),
                str(attachment.get('conversation_id', 'N/A'))
            ]
            
            # Add table row
            attachment_lines.append("| " + " | ".join(values) + " |")
        
        return '\n'.join(attachment_lines)

    def _detect_content_loss(self, original_html: str, converted_text: str) -> bool:
        """
        Detect if significant content was lost during conversion.
        
        Args:
            original_html: Original HTML content
            converted_text: Converted plain text
            
        Returns:
            True if significant content loss detected, False otherwise
        """
        # Extract key information from both versions
        original_soup = BeautifulSoup(original_html, 'html.parser')
        converted_soup = BeautifulSoup(converted_text, 'html.parser')
        
        # Check for key content indicators
        original_text = original_soup.get_text()
        converted_text_clean = converted_text.strip()
        
        # Calculate content preservation ratio
        if len(original_text) == 0:
            return False  # No content to lose
        
        preservation_ratio = len(converted_text_clean) / len(original_text)
        
        # If we preserved less than 60% of content, consider it significant loss
        if preservation_ratio < 0.6:
            print(f"⚠️ Content loss detected: {preservation_ratio:.1%} preserved")
            return True
        
        # Check for specific content patterns that might indicate loss
        # Look for common email content patterns
        email_patterns = [
            'subject', 'from', 'to', 'cc', 'date', 'time', 'message', 'body',
            'attachment', 'file', 'download', 'click', 'link', 'url'
        ]
        
        original_has_patterns = any(pattern in original_text.lower() for pattern in email_patterns)
        converted_has_patterns = any(pattern in converted_text_clean.lower() for pattern in email_patterns)
        
        if original_has_patterns and not converted_has_patterns:
            print("⚠️ Email content patterns lost during conversion")
            return True
        
        return False

    def _is_google_calendar_table(self, table) -> bool:
        """
        Detects if a table is from Google Calendar based on content and structure.
        """
        table_text = table.get_text().lower()
        google_calendar_indicators = [
            'meet.google.com',
            'join with google meet',
            'meeting link',
            'join by phone',
            'calendar.google.com',
            'view map',
            'view all guest info'
        ]
        
        # Check if table contains Google Calendar indicators
        has_google_content = any(indicator in table_text for indicator in google_calendar_indicators)
        
        # Check if table has complex nested structure (typical of Google Calendar)
        nested_tables = table.find_all('table')
        has_nested_structure = len(nested_tables) > 0
        
        # Check if table has many cells with similar content (duplication indicator)
        rows = table.find_all('tr')
        if rows:
            all_cells = []
            for row in rows:
                cells = row.find_all(['td', 'th'])
                for cell in cells:
                    cell_text = cell.get_text().strip()
                    if cell_text:
                        all_cells.append(cell_text)
            
            # If we have many cells with similar content, it's likely a Google Calendar table
            if len(all_cells) > 10:
                # Check for repeated patterns
                unique_cells = set(all_cells)
                if len(unique_cells) < len(all_cells) * 0.7:  # If more than 30% are duplicates
                    return True
        
        return has_google_content and has_nested_structure
    
    def _extract_google_calendar_table_content(self, table) -> str:
        """
        Extracts meaningful content from Google Calendar tables without duplication.
        """
        # Extract key meeting information without the complex table structure
        meeting_info = []
        
        # Look for meeting title/description
        title_cells = table.find_all(['td', 'th'], string=lambda x: x and len(x.strip()) > 20)
        for cell in title_cells:
            text = cell.get_text().strip()
            if text and not any(existing in text for existing in meeting_info):
                meeting_info.append(text)
        
        # Look for meeting time
        time_cells = table.find_all(['td', 'th'], string=lambda x: x and any(time_indicator in x.lower() for time_indicator in ['am', 'pm', ':', '2024']))
        for cell in time_cells:
            text = cell.get_text().strip()
            if text and not any(existing in text for existing in meeting_info):
                meeting_info.append(text)
        
        # Look for location
        location_cells = table.find_all(['td', 'th'], string=lambda x: x and any(loc_indicator in x.lower() for loc_indicator in ['floor', 'plot', 'sector', 'gurugram', 'haryana']))
        for cell in location_cells:
            text = cell.get_text().strip()
            if text and not any(existing in text for existing in meeting_info):
                meeting_info.append(text)
        
        # Look for meeting links
        link_cells = table.find_all(['td', 'th'])
        for cell in link_cells:
            links = cell.find_all('a', href=True)
            for link in links:
                href = link.get('href')
                if 'meet.google.com' in href or 'calendar.google.com' in href:
                    text = link.get_text().strip()
                    if text and not any(existing in text for existing in meeting_info):
                        meeting_info.append(f"{text}: {href}")
        
        # If we found meaningful content, return it
        if meeting_info:
            return '\n\n'.join(meeting_info)
        
        # Fallback: extract unique text content
        all_text = []
        for cell in table.find_all(['td', 'th']):
            text = cell.get_text().strip()
            if text and len(text) > 5 and text not in all_text:
                all_text.append(text)
        
        return '\n'.join(all_text)
