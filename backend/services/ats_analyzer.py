import re
import os
from typing import List, Dict, Any, Tuple
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from backend.services.cv_parser import COMMON_SKILLS

class ATSAnalyzer:
    @staticmethod
    def extract_keywords_from_jd(jd_text: str) -> List[str]:
        """Extracts recognizable skills and key terms from the job description."""
        jd_lower = jd_text.lower()
        extracted = []
        for skill in COMMON_SKILLS:
            if len(skill) <= 3:
                pattern = r'\b' + re.escape(skill) + r'\b'
            else:
                pattern = re.escape(skill)
                
            if re.search(pattern, jd_lower):
                if skill == "golang":
                    skill = "Go"
                elif skill == "nodejs":
                    skill = "Node.js"
                extracted.append(skill.title() if len(skill) > 3 else skill.upper())
        return list(set(extracted))

    @classmethod
    def analyze_ats(cls, cv_text: str, jd_text: str) -> Dict[str, Any]:
        cv_lower = cv_text.lower()
        jd_skills = cls.extract_keywords_from_jd(jd_text)
        
        if not jd_skills:
            # Fallback if no specific tech skills found
            return {
                "score": 70,
                "matched_skills": [],
                "missing_skills": [],
                "recommendations": [
                    "We didn't detect specific technical keywords in this job description. Make sure your resume is formatted clearly with sections for Experience and Education."
                ]
            }

        matched_skills = []
        missing_skills = []

        for skill in jd_skills:
            skill_lower = skill.lower()
            if len(skill_lower) <= 3:
                pattern = r'\b' + re.escape(skill_lower) + r'\b'
            else:
                pattern = re.escape(skill_lower)

            if re.search(pattern, cv_lower):
                matched_skills.append(skill)
            else:
                missing_skills.append(skill)

        # Calculate score
        match_ratio = len(matched_skills) / len(jd_skills)
        score = int(match_ratio * 100)

        # Ensure realistic limits
        score = max(0, min(100, score))  # Natural 0-100 range

        # Generate recommendations
        recommendations = []
        if score < 40:
            recommendations.append("🚨 Critical: This CV is not aligned with this role. Major skill gaps detected.")
        elif score < 75:
            recommendations.append("⚠️ Good start, but you need to optimize this CV to stand out in the applicant pool.")
        else:
            recommendations.append("✨ Excellent! Your profile is highly relevant for this position.")

        if missing_skills:
            recommendations.append(f"Add the following missing keywords to your Skills or Professional Summary section: {', '.join(missing_skills[:5])}.")
        
        recommendations.append("Ensure your experience section lists achievements with quantifiable metrics (e.g., 'Improved performance by 25%', 'Led a team of 4 engineers').")
        recommendations.append("Avoid complex multi-column layouts, graphics, or tables, as standard ATS scanners may fail to parse them correctly.")

        return {
            "score": score,
            "matched_skills": sorted(matched_skills),
            "missing_skills": sorted(missing_skills),
            "recommendations": recommendations
        }

    @classmethod
    def tailor_cv(cls, cv_text: str, job_description: str, job_title: str, company_name: str, missing_skills: List[str]) -> Tuple[str, str]:
        """
        Creates a tailored text representation of the CV and generates a beautifully formatted PDF.
        """
        # Clean and split text
        lines = [line.strip() for line in cv_text.split("\n") if line.strip()]
        
        from backend.services.cv_parser import CVParser
        
        # Use CVParser to extract structured details (name, email, phone)
        parsed = CVParser.parse_cv(cv_text.encode("utf-8", errors="ignore"), "cv.txt")
        candidate_name = parsed.get("name") or "Candidate Name"
        candidate_email = parsed.get("email") or "contact@candidate.com"
        candidate_phone = parsed.get("phone") or ""
        
        # 1. Classify lines into blocks using a robust state machine
        header_block = []
        experience_block = []
        education_block = []
        skills_block = []
        
        current_section = "header"
        
        for line in lines:
            line_lower = line.lower()
            
            # Detect section transitions explicitly
            if any(k in line_lower for k in ["education", "academic", "university", "college"]):
                current_section = "education"
                continue
            elif any(k in line_lower for k in ["skills", "technologies", "expertise"]):
                current_section = "skills"
                continue
            elif any(k in line_lower for k in ["experience", "employment", "history", "work"]):
                current_section = "experience"
                continue
            elif any(k in line_lower for k in ["languages", "certifications", "projects"]):
                current_section = "other"
                continue
            
            # Auto-detect experience section when seeing job indicators in the header
            if current_section == "header":
                has_date = bool(re.search(r'\b(19|20)\d{2}\b', line_lower))
                has_pipe = "|" in line
                if has_date or has_pipe or line_lower.startswith("led ") or line_lower.startswith("built ") or line_lower.startswith("developed "):
                    current_section = "experience"
            
            if current_section == "header":
                header_block.append(line)
            elif current_section == "experience":
                experience_block.append(line)
            elif current_section == "education":
                education_block.append(line)
            elif current_section == "skills":
                skills_block.append(line)

        # 2. Re-create the CV with tailored improvements
        tailored_lines = []
        
        tailored_lines.append(candidate_name)
        tailored_lines.append(f"Targeting: {job_title} at {company_name}")
        
        contact_line_parts = []
        if candidate_email:
            contact_line_parts.append(candidate_email)
        if candidate_phone:
            contact_line_parts.append(candidate_phone)
        if contact_line_parts:
            tailored_lines.append(" | ".join(contact_line_parts))
        tailored_lines.append("")
        
        # Skills section (Incorporate missing skills)
        existing_skills_text = ", ".join(skills_block) if skills_block else ", ".join(parsed.get("skills", []))
        if not existing_skills_text:
            existing_skills_text = "Software Development, System Architecture"
            
        all_skills = [s.strip() for s in existing_skills_text.split(",") if s.strip()]
        
        # Add target/missing skills
        for ms in missing_skills:
            if ms.lower() not in [es.lower() for es in all_skills]:
                all_skills.append(ms)

        # Professional Summary
        summary_text = (
            f"Dedicated and results-driven professional targeting the {job_title} role at {company_name}. "
            f"Proven ability to engineer high-quality solutions, leveraging expertise in {', '.join(all_skills[:4])}. "
            f"Skilled in designing scalable architectures, optimizing workflow performance, and collaborating "
            f"in cross-functional environments to deliver critical deliverables aligned with job requirements."
        )
        
        tailored_lines.append("PROFESSIONAL SUMMARY")
        tailored_lines.append(summary_text)
        tailored_lines.append("")
        
        tailored_lines.append("CORE SKILLS & TECHNOLOGIES")
        tailored_lines.append(", ".join(all_skills))
        tailored_lines.append("")
 
        # Experience
        tailored_lines.append("PROFESSIONAL EXPERIENCE")
        tailored_experience_block = []
        if experience_block:
            injected = False
            for exp_line in experience_block:
                # Classify line to see if it is a descriptive bullet point or a header
                is_bullet = not ("|" in exp_line or any(m in exp_line.lower() for m in ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "present"]))
                if exp_line.startswith("-") or exp_line.startswith("•") or exp_line.startswith("–") or exp_line.startswith("*"):
                    is_bullet = True
                    
                if is_bullet and not injected and missing_skills:
                    bullet = f"• Integrated {', '.join(missing_skills[:3])} to optimize project workflows and technical delivery."
                    tailored_lines.append(bullet)
                    tailored_experience_block.append(bullet)
                    injected = True
                    
                tailored_lines.append(exp_line)
                tailored_experience_block.append(exp_line)
        else:
            fallback_lines = [
                f"Software Engineer / Developer | Previous Company",
                f"• Led development of critical products, applying modern architecture patterns."
            ]
            if missing_skills:
                fallback_lines.append(f"• Leveraged {', '.join(missing_skills[:3])} to build resilient and scalable solutions.")
            fallback_lines.append(f"• Partnered with product and design teams to refine requirements and deliverables.")
            
            for fbl in fallback_lines:
                tailored_lines.append(fbl)
                tailored_experience_block.append(fbl)
                
        tailored_lines.append("")

        # Education
        tailored_lines.append("EDUCATION")
        if education_block:
            tailored_lines.extend(education_block)
        else:
            tailored_lines.append("B.S. in Computer Science or Equivalent")
            tailored_lines.append("Relevant Courses: Algorithms, Database Management, System Design")

        tailored_text = "\n".join(tailored_lines)

        # XML Escape helper for ReportLab
        import xml.sax.saxutils as saxutils
        def escape_xml(text):
            if not isinstance(text, str):
                return text
            return saxutils.escape(text)

        # Generate a premium PDF using reportlab
        os.makedirs("backend/data/tailored", exist_ok=True)
        import uuid
        pdf_filename = f"tailored_cv_{uuid.uuid4().hex[:16]}.pdf"
        pdf_path = f"backend/data/tailored/{pdf_filename}"
        
        cls._generate_pdf_reportlab(
            pdf_path=pdf_path,
            name=escape_xml(candidate_name),
            email=escape_xml(candidate_email),
            phone=escape_xml(candidate_phone),
            job_title=escape_xml(job_title),
            company=escape_xml(company_name),
            skills=[escape_xml(s) for s in all_skills],
            experience=[escape_xml(e) for e in tailored_experience_block],
            education=[escape_xml(e) for e in education_block],
            summary_text=escape_xml(summary_text)
        )

        # Trigger cleanup of old PDFs
        cls._cleanup_old_pdfs()

        # Return the tailored text and the relative static URL to download the PDF
        download_url = f"/static/tailored/{pdf_filename}"
        return tailored_text, download_url

    @classmethod
    def _cleanup_old_pdfs(cls):
        """Deletes PDF files older than 1 hour to prevent disk space exhaustion."""
        import time
        directory = "backend/data/tailored"
        if not os.path.exists(directory):
            return
        current_time = time.time()
        for filename in os.listdir(directory):
            if filename.endswith(".pdf"):
                filepath = os.path.join(directory, filename)
                try:
                    # If older than 3600 seconds (1 hour)
                    if os.path.getmtime(filepath) < current_time - 3600:
                        os.remove(filepath)
                except Exception:
                    pass

    @staticmethod
    def _generate_pdf_reportlab(pdf_path: str, name: str, email: str, phone: str, job_title: str, company: str, skills: List[str], experience: List[str], education: List[str], summary_text: str):
        """Generates a professional, premium single-page style PDF CV."""
        doc = SimpleDocTemplate(pdf_path, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        story = []

        styles = getSampleStyleSheet()
        
        # Define clean premium styling
        primary_color = colors.HexColor("#1e293b")  # Slate 800
        secondary_color = colors.HexColor("#4f46e5")  # Indigo 600
        text_color = colors.HexColor("#334155")  # Slate 700
        
        name_style = ParagraphStyle(
            'NameStyle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=20,
            leading=24,
            textColor=primary_color,
            spaceAfter=2
        )
        
        subtitle_style = ParagraphStyle(
            'SubtitleStyle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=13,
            textColor=secondary_color,
            spaceAfter=4
        )

        contact_style = ParagraphStyle(
            'ContactStyle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=11,
            textColor=text_color,
            spaceAfter=8
        )

        section_heading = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=10.5,
            leading=14,
            textColor=primary_color,
            spaceBefore=0,
            spaceAfter=0,
            keepWithNext=True
        )

        body_style = ParagraphStyle(
            'BodyStyle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=13,
            textColor=text_color,
            spaceAfter=4
        )

        bullet_style = ParagraphStyle(
            'BulletStyle',
            parent=body_style,
            leftIndent=15,
            firstLineIndent=-10,
            spaceAfter=3
        )

        # Helper function to create section divider table
        def create_section_header(title: str):
            t = Table([[Paragraph(title, section_heading)]], colWidths=[532])
            t.setStyle(TableStyle([
                ('LINEBELOW', (0,0), (-1,-1), 0.75, colors.HexColor("#cbd5e1")), # Slate 300 line
                ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                ('TOPPADDING', (0,0), (-1,-1), 10),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ]))
            return t

        # Top Accent Bar
        top_bar = Table([[""]], colWidths=[532], rowHeights=[3])
        top_bar.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), secondary_color),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(top_bar)
        story.append(Spacer(1, 10))

        # Header Info
        story.append(Paragraph(name, name_style))
        story.append(Paragraph(f"Optimized for: {job_title} | {company}", subtitle_style))
        
        # Email / Phone info matching
        contact_line_parts = []
        if email:
            contact_line_parts.append(email)
        if phone:
            contact_line_parts.append(phone)
        contact_line = "  |  ".join(contact_line_parts)
        if not contact_line:
            contact_line = "Email: contact@candidate.com  |  Phone: (555) 019-2834"
        story.append(Paragraph(contact_line, contact_style))
        
        # Professional Summary Section
        story.append(create_section_header("PROFESSIONAL SUMMARY"))
        story.append(Spacer(1, 4))
        story.append(Paragraph(summary_text, body_style))

        # Core Skills Section
        story.append(create_section_header("TECHNICAL PROFILE"))
        story.append(Spacer(1, 4))
        skills_text = ", ".join(skills)
        story.append(Paragraph(skills_text, body_style))

        # Professional Experience Section
        story.append(create_section_header("PROFESSIONAL EXPERIENCE"))
        story.append(Spacer(1, 4))
        if experience:
            for item in experience[:15]:  # Guard against page overflow
                clean_item = item.strip()
                if not clean_item:
                    continue
                    
                # Classify item: job header vs description bullet point
                is_header = "|" in clean_item or "@" in clean_item or any(m in clean_item.lower() for m in ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "present"])
                
                # Bullet point cleaning
                if clean_item.startswith("-") or clean_item.startswith("•") or clean_item.startswith("–") or clean_item.startswith("*"):
                    clean_item = clean_item.lstrip("- •*–")
                    is_header = False
                    
                if is_header:
                    # Make section sub-headers bold (e.g. role and company)
                    story.append(Paragraph(f"<b>{clean_item}</b>", body_style))
                else:
                    story.append(Paragraph(f"&bull; {clean_item}", bullet_style))
        else:
            story.append(Paragraph(f"<b>Software Engineer | Achievements</b>", body_style))
            story.append(Paragraph(f"&bull; Developed and deployed modern responsive components and services matching {company} standards.", bullet_style))
            story.append(Paragraph(f"&bull; Streamlined project architecture, successfully implementing features based on {', '.join(skills[:3])}.", bullet_style))
        
        # Education Section
        story.append(create_section_header("EDUCATION & CREDENTIALS"))
        story.append(Spacer(1, 4))
        if education:
            for item in education[:4]:
                clean_item = item.strip()
                if not clean_item:
                    continue
                story.append(Paragraph(clean_item, body_style))
        else:
            story.append(Paragraph("<b>Bachelor of Science in Computer Science</b>", body_style))
            story.append(Paragraph("GPA: 3.8/4.0  |  Relevant coursework: Algorithms, Distributed Systems, Web Programming", body_style))

        # Branding Footer
        branding_style = ParagraphStyle(
            'BrandingStyle',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#94a3b8"),
            alignment=1,  # Center
            spaceBefore=15
        )
        story.append(Spacer(1, 10))
        story.append(Paragraph("Powered by Line Driven Solution", branding_style))

        # Build Document
        doc.build(story)
